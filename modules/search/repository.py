"""Search 모듈 리포지토리 계층

MongoDB 및 Redis 캐시와의 상호작용을 담당
검색 로그, 메타데이터, 캐시, 통계 관리
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from infra.database import get_database

from .schema import SearchLog, SearchResult, SearchStats
from .cache_manager import SearchCacheManager, get_search_cache_manager

logger = structlog.get_logger(__name__)


class SearchRepository:
    """검색 관련 데이터 접근 계층"""
    
    def __init__(self):
        """SearchRepository 초기화"""
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.cache_manager: Optional[SearchCacheManager] = None
        self._initialized = False
        
    async def _ensure_initialized(self) -> None:
        """리포지토리 초기화 확인"""
        if not self._initialized:
            self.db = get_database()
            self.cache_manager = await get_search_cache_manager()
            self._initialized = True
            logger.info("SearchRepository 초기화 완료")
    
    # === 검색 로그 관리 ===
    
    async def search_repo_log_query(
        self, 
        query_text: str, 
        results: List[SearchResult],
        search_mode: str,
        filters: Optional[Dict[str, Any]] = None,
        search_time_ms: int = 0,
        user_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """검색 질의 및 결과 로그 저장
        
        Args:
            query_text: 검색 질의 텍스트
            results: 검색 결과 목록
            search_mode: 검색 모드
            filters: 적용된 필터
            search_time_ms: 검색 소요 시간
            user_id: 사용자 ID
            error_message: 에러 메시지 (실패 시)
            
        Returns:
            query_id: 생성된 검색 ID
        """
        await self._ensure_initialized()
        
        try:
            # 검색 ID 생성
            query_id = self._generate_query_id(query_text, user_id)
            
            # 로그 데이터 구성
            log_data = {
                "query_id": query_id,
                "user_id": user_id,
                "query_text": query_text,
                "search_mode": search_mode,
                "filters": filters,
                "result_count": len(results),
                "search_time_ms": search_time_ms,
                "timestamp": datetime.now(),
                "success": error_message is None,
                "error_message": error_message,
                "result_ids": [r.document_id for r in results] if results else []
            }
            
            # MongoDB에 저장
            collection = self.db.search_logs
            await collection.insert_one(log_data)
            
            logger.info(
                "검색 로그 저장 완료",
                query_id=query_id,
                result_count=len(results),
                search_time_ms=search_time_ms
            )
            
            # 캐시에도 최근 검색 저장 (빠른 조회용)
            await self.cache_manager.cache_recent_search(
                user_id or "anonymous",
                query_id,
                log_data
            )
            
            return query_id
            
        except Exception as e:
            logger.error("검색 로그 저장 실패", error=str(e))
            # 로깅 실패해도 검색은 계속 진행
            return self._generate_query_id(query_text, user_id)
    
    async def search_repo_get_search_history(
        self, 
        user_id: str, 
        limit: int = 20,
        offset: int = 0
    ) -> List[SearchLog]:
        """사용자의 검색 이력 조회
        
        Args:
            user_id: 사용자 ID
            limit: 조회할 개수
            offset: 오프셋
            
        Returns:
            검색 로그 목록
        """
        await self._ensure_initialized()
        
        try:
            collection = self.db.search_logs
            
            # 최근 검색부터 조회
            cursor = collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).skip(offset).limit(limit)
            
            logs = []
            async for doc in cursor:
                # _id 필드 제거 후 SearchLog 모델로 변환
                doc.pop("_id", None)
                logs.append(SearchLog(**doc))
            
            return logs
            
        except Exception as e:
            logger.error("검색 이력 조회 실패", user_id=user_id, error=str(e))
            return []
    
    # === 메타데이터 조회 ===
    
    async def search_repo_get_metadata(
        self, 
        document_ids: List[str]
    ) -> Dict[str, Any]:
        """문서 ID 목록에 대한 메타데이터 조회
        
        Args:
            document_ids: 문서 ID 목록
            
        Returns:
            문서 ID를 키로 하는 메타데이터 딕셔너리
        """
        await self._ensure_initialized()
        
        if not document_ids:
            return {}
        
        try:
            # 먼저 캐시에서 조회
            metadata_dict = {}
            uncached_ids = []
            
            for doc_id in document_ids:
                cached_data = await self.cache_manager.cache_document_metadata_get(doc_id)
                
                if cached_data:
                    metadata_dict[doc_id] = cached_data
                else:
                    uncached_ids.append(doc_id)
            
            # 캐시에 없는 것들은 DB에서 조회
            if uncached_ids:
                collection = self.db.emails  # 이메일 컬렉션 사용
                
                cursor = collection.find(
                    {"_id": {"$in": uncached_ids}},
                    {
                        "_id": 1,
                        "subject": 1,
                        "sender": 1,
                        "recipients": 1,
                        "date": 1,
                        "attachments": 1,
                        "tags": 1,
                        "content": 1,
                        "thread_id": 1
                    }
                )
                
                async for doc in cursor:
                    doc_id = str(doc["_id"])
                    doc["_id"] = doc_id
                    metadata_dict[doc_id] = doc
                    
                    # 캐시에 저장
                    await self.cache_manager.cache_document_metadata_set(doc_id, doc)
            
            return metadata_dict
            
        except Exception as e:
            logger.error("메타데이터 조회 실패", error=str(e))
            return {}
    
    async def search_repo_get_email_details(
        self, 
        email_id: str
    ) -> Optional[Dict[str, Any]]:
        """이메일 상세 정보 조회
        
        Args:
            email_id: 이메일 ID
            
        Returns:
            이메일 상세 정보 또는 None
        """
        await self._ensure_initialized()
        
        try:
            # 캐시에서 먼저 확인
            cached_data = await self.cache_manager.cache_email_metadata_get(email_id)
            
            if cached_data:
                return cached_data
            
            # DB에서 조회
            collection = self.db.emails
            doc = await collection.find_one({"_id": email_id})
            
            if doc:
                doc["_id"] = str(doc["_id"])
                # 캐시에 저장
                await self.cache_manager.cache_email_metadata_set(email_id, doc)
                return doc
            
            return None
            
        except Exception as e:
            logger.error("이메일 상세 조회 실패", email_id=email_id, error=str(e))
            return None
    
    # === 캐시 관리 ===
    
    async def search_repo_cache_get(
        self, 
        key: str
    ) -> Optional[Any]:
        """캐시에서 데이터 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 데이터 또는 None
        """
        await self._ensure_initialized()
        
        try:
            return await self.cache_manager.cache_get(key)
        except Exception as e:
            logger.error("캐시 조회 실패", key=key, error=str(e))
            return None
    
    async def search_repo_cache_set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600
    ) -> bool:
        """캐시에 데이터 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL(초)
            
        Returns:
            저장 성공 여부
        """
        await self._ensure_initialized()
        
        try:
            return await self.cache_manager.cache_set(key, value, ttl)
        except Exception as e:
            logger.error("캐시 저장 실패", key=key, error=str(e))
            return False
    
    async def search_repo_cache_delete(
        self, 
        key: str
    ) -> bool:
        """캐시에서 데이터 삭제
        
        Args:
            key: 캐시 키
            
        Returns:
            삭제 성공 여부
        """
        await self._ensure_initialized()
        
        try:
            # cache_manager는 delete 메서드가 없으므로 직접 infra cache 사용
            # 또는 cache_manager에 delete 메서드 추가 필요
            return await self.cache_manager.cache.cache_delete(key)
        except Exception as e:
            logger.error("캐시 삭제 실패", key=key, error=str(e))
            return False
    
    # === 통계 관리 ===
    
    async def search_repo_update_stats(
        self, 
        query_type: str, 
        response_time: float,
        success: bool = True,
        search_mode: str = "hybrid",
        collection_name: str = "emails"
    ) -> None:
        """검색 통계 업데이트
        
        Args:
            query_type: 질의 유형
            response_time: 응답 시간(초)
            success: 성공 여부
            search_mode: 검색 모드
            collection_name: 컬렉션 이름
        """
        await self._ensure_initialized()
        
        try:
            collection = self.db.search_stats
            
            # 현재 시간 기준 통계 키 생성 (시간별 통계)
            now = datetime.now()
            stat_key = now.strftime("%Y%m%d%H")
            
            # 업데이트할 필드들
            update_fields = {
                "$inc": {
                    "total_searches": 1,
                    f"search_modes_distribution.{search_mode}": 1,
                    f"collections_usage.{collection_name}": 1
                },
                "$push": {
                    "response_times": {
                        "$each": [response_time * 1000],  # ms로 변환
                        "$slice": -1000  # 최근 1000개만 유지
                    }
                },
                "$set": {
                    "period_end": now
                },
                "$setOnInsert": {
                    "period_start": now.replace(minute=0, second=0, microsecond=0)
                }
            }
            
            if success:
                update_fields["$inc"]["successful_searches"] = 1
            else:
                update_fields["$inc"]["failed_searches"] = 1
            
            # 통계 업데이트 (upsert)
            await collection.update_one(
                {"stat_key": stat_key},
                update_fields,
                upsert=True
            )
            
            # 인기 검색어 업데이트 (별도 컬렉션)
            if query_type:
                await self._update_popular_queries(query_type)
            
        except Exception as e:
            logger.error("통계 업데이트 실패", error=str(e))
    
    async def search_repo_get_stats(
        self, 
        period_hours: int = 24
    ) -> Optional[SearchStats]:
        """검색 통계 조회
        
        Args:
            period_hours: 조회할 기간(시간)
            
        Returns:
            검색 통계 또는 None
        """
        await self._ensure_initialized()
        
        try:
            collection = self.db.search_stats
            
            # 기간 계산
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=period_hours)
            
            # 집계 파이프라인
            pipeline = [
                {
                    "$match": {
                        "period_start": {"$gte": start_time}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_searches": {"$sum": "$total_searches"},
                        "successful_searches": {"$sum": "$successful_searches"},
                        "failed_searches": {"$sum": "$failed_searches"},
                        "response_times": {"$push": "$response_times"},
                        "search_modes_distribution": {"$mergeObjects": "$search_modes_distribution"},
                        "collections_usage": {"$mergeObjects": "$collections_usage"}
                    }
                }
            ]
            
            cursor = collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if not result:
                return None
            
            stats_data = result[0]
            
            # 평균 응답 시간 계산
            all_response_times = []
            for times in stats_data.get("response_times", []):
                if isinstance(times, list):
                    all_response_times.extend(times)
            
            avg_response_time = (
                sum(all_response_times) / len(all_response_times)
                if all_response_times else 0.0
            )
            
            # 캐시 히트율 계산 (캐시 관리자에서 가져오기)
            cache_stats = self.cache_manager.get_cache_stats()
            cache_hit_rate = cache_stats.get("hit_rate", 0.0)
            
            # 인기 검색어 조회
            popular_queries = await self._get_popular_queries(limit=10)
            
            return SearchStats(
                total_searches=stats_data.get("total_searches", 0),
                successful_searches=stats_data.get("successful_searches", 0),
                failed_searches=stats_data.get("failed_searches", 0),
                average_response_time_ms=avg_response_time,
                cache_hit_rate=cache_hit_rate,
                popular_queries=popular_queries,
                search_modes_distribution=stats_data.get("search_modes_distribution", {}),
                collections_usage=stats_data.get("collections_usage", {}),
                period_start=start_time,
                period_end=end_time
            )
            
        except Exception as e:
            logger.error("통계 조회 실패", error=str(e))
            return None
    
    # === 내부 헬퍼 메서드 ===
    
    def _generate_query_id(self, query_text: str, user_id: Optional[str]) -> str:
        """검색 ID 생성
        
        Args:
            query_text: 검색어
            user_id: 사용자 ID
            
        Returns:
            생성된 검색 ID
        """
        # 타임스탬프와 검색어를 조합하여 유니크한 ID 생성
        timestamp = str(time.time())
        content = f"{query_text}:{user_id or 'anonymous'}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def _update_popular_queries(self, query_text: str) -> None:
        """인기 검색어 업데이트
        
        Args:
            query_text: 검색어
        """
        try:
            collection = self.db.popular_queries
            
            # 검색어 카운트 증가
            await collection.update_one(
                {"query": query_text},
                {
                    "$inc": {"count": 1},
                    "$set": {"last_searched": datetime.now()}
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error("인기 검색어 업데이트 실패", error=str(e))
    
    async def _get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """인기 검색어 조회
        
        Args:
            limit: 조회할 개수
            
        Returns:
            인기 검색어 목록
        """
        try:
            collection = self.db.popular_queries
            
            # 최근 7일간의 인기 검색어
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            cursor = collection.find(
                {"last_searched": {"$gte": seven_days_ago}}
            ).sort("count", -1).limit(limit)
            
            queries = []
            async for doc in cursor:
                queries.append({
                    "query": doc["query"],
                    "count": doc["count"],
                    "last_searched": doc["last_searched"].isoformat()
                })
            
            return queries
            
        except Exception as e:
            logger.error("인기 검색어 조회 실패", error=str(e))
            return []
