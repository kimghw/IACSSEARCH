"""Search 모듈 전용 캐시 관리자

Search 모듈 내에서만 사용되는 캐시 키 생성, 관리, 정책을 통합 관리
중앙 캐시 서비스(infra/cache.py)를 사용하되, search 전용 로직은 여기서 처리
"""

import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from infra.cache import CacheService, get_cache_service

logger = structlog.get_logger(__name__)


class SearchCacheKeys:
    """Search 모듈 전용 캐시 키 정의"""
    
    # 검색 전용 캐시 키 패턴
    EMBEDDING = "search:embedding:{text_hash}"
    PROCESSED_QUERY = "search:processed_query:{query_hash}"
    VECTOR_RESULTS = "search:vector:results:{query_hash}:{collection}"
    ENRICHED_RESULTS = "search:enriched:{result_hash}"
    
    # 메타데이터 캐시
    EMAIL_METADATA = "search:email:{email_id}"
    DOCUMENT_METADATA = "search:metadata:{doc_id}"
    
    # 사용자별 캐시
    RECENT_SEARCHES = "search:recent:{user_id}:{query_id}"
    USER_PREFERENCES = "search:prefs:{user_id}"
    
    # 성능 모니터링 캐시
    PERFORMANCE_METRICS = "search:perf:ops:{operation}:{timestamp}"
    BOTTLENECK_ANALYSIS = "search:perf:bottlenecks"
    
    # 임시 캐시
    QUERY_SUGGESTIONS = "search:suggestions:{partial_query}"
    COLLECTION_INFO = "search:collections:info"


class SearchCacheTTL:
    """Search 모듈 캐시 TTL 정책"""
    
    # 장기 캐시 (1시간 이상)
    EMBEDDING = 3600  # 1시간 - 임베딩은 변경되지 않음
    PROCESSED_QUERY = 3600  # 1시간 - 처리된 쿼리
    EMAIL_METADATA = 3600  # 1시간 - 이메일 메타데이터
    
    # 중기 캐시 (10분 ~ 1시간)
    DOCUMENT_METADATA = 1800  # 30분 - 문서 메타데이터
    ENRICHED_RESULTS = 1200  # 20분 - 보강된 결과
    VECTOR_RESULTS = 600  # 10분 - 벡터 검색 결과
    
    # 단기 캐시 (10분 미만)
    RECENT_SEARCHES = 300  # 5분 - 최근 검색
    QUERY_SUGGESTIONS = 300  # 5분 - 쿼리 제안
    
    # 장기 통계 (24시간)
    PERFORMANCE_METRICS = 86400  # 24시간 - 성능 메트릭
    BOTTLENECK_ANALYSIS = 3600  # 1시간 - 병목 분석
    
    # 세션 캐시
    USER_PREFERENCES = 7200  # 2시간 - 사용자 선호도
    COLLECTION_INFO = 1800  # 30분 - 컬렉션 정보


class SearchCacheManager:
    """Search 모듈 전용 캐시 관리자"""
    
    def __init__(self):
        """SearchCacheManager 초기화"""
        self.cache: Optional[CacheService] = None
        self._initialized = False
        self.keys = SearchCacheKeys()
        self.ttl = SearchCacheTTL()
        
        # 캐시 통계
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0
        }
    
    async def _ensure_initialized(self) -> None:
        """서비스 초기화 확인"""
        if not self._initialized:
            self.cache = await get_cache_service()
            self._initialized = True
            logger.info("SearchCacheManager 초기화 완료")
    
    # === 임베딩 캐시 ===
    
    async def cache_embedding_get(self, text: str) -> Optional[List[float]]:
        """임베딩 캐시 조회
        
        Args:
            text: 임베딩을 조회할 텍스트
            
        Returns:
            캐시된 임베딩 또는 None
        """
        await self._ensure_initialized()
        
        try:
            cache_key = self._generate_text_hash(text)
            key = self.keys.EMBEDDING.format(text_hash=cache_key)
            
            cached_data = await self.cache.cache_get(key)
            if cached_data and isinstance(cached_data, dict):
                embedding = cached_data.get("embedding")
                if embedding and isinstance(embedding, list):
                    # 캐시 유효성 검사
                    cached_time = cached_data.get("cached_at", 0)
                    if time.time() - cached_time < self.ttl.EMBEDDING:
                        self._stats["hits"] += 1
                        logger.debug("임베딩 캐시 히트", text_preview=text[:30])
                        return embedding
            
            self._stats["misses"] += 1
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("임베딩 캐시 조회 실패", error=str(e))
            return None
    
    async def cache_embedding_set(
        self,
        text: str,
        embedding: List[float]
    ) -> bool:
        """임베딩 캐시 저장
        
        Args:
            text: 원본 텍스트
            embedding: 저장할 임베딩
            
        Returns:
            저장 성공 여부
        """
        await self._ensure_initialized()
        
        try:
            cache_key = self._generate_text_hash(text)
            key = self.keys.EMBEDDING.format(text_hash=cache_key)
            
            cache_data = {
                "embedding": embedding,
                "text_preview": text[:100],
                "cached_at": time.time(),
                "model": "text-embedding-ada-002"
            }
            
            await self.cache.cache_set(key, cache_data, ttl=self.ttl.EMBEDDING)
            logger.debug("임베딩 캐시 저장", text_preview=text[:30])
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("임베딩 캐시 저장 실패", error=str(e))
            return False
    
    # === 처리된 쿼리 캐시 ===
    
    async def cache_processed_query_get(
        self,
        query_text: str
    ) -> Optional[Dict[str, Any]]:
        """처리된 쿼리 캐시 조회"""
        await self._ensure_initialized()
        
        try:
            cache_key = self._generate_query_hash(query_text)
            key = self.keys.PROCESSED_QUERY.format(query_hash=cache_key)
            
            cached_data = await self.cache.cache_get(key)
            if cached_data:
                self._stats["hits"] += 1
                return cached_data
            
            self._stats["misses"] += 1
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("처리된 쿼리 캐시 조회 실패", error=str(e))
            return None
    
    async def cache_processed_query_set(
        self,
        query_text: str,
        processed_data: Dict[str, Any]
    ) -> bool:
        """처리된 쿼리 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            cache_key = self._generate_query_hash(query_text)
            key = self.keys.PROCESSED_QUERY.format(query_hash=cache_key)
            
            await self.cache.cache_set(key, processed_data, ttl=self.ttl.PROCESSED_QUERY)
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("처리된 쿼리 캐시 저장 실패", error=str(e))
            return False
    
    # === 벡터 검색 결과 캐시 ===
    
    async def cache_vector_results_get(
        self,
        query_hash: str,
        collection: str
    ) -> Optional[List[Dict[str, Any]]]:
        """벡터 검색 결과 캐시 조회"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.VECTOR_RESULTS.format(
                query_hash=query_hash,
                collection=collection
            )
            
            cached_data = await self.cache.cache_get(key)
            if cached_data:
                self._stats["hits"] += 1
                return cached_data
            
            self._stats["misses"] += 1
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("벡터 결과 캐시 조회 실패", error=str(e))
            return None
    
    async def cache_vector_results_set(
        self,
        query_hash: str,
        collection: str,
        results: List[Dict[str, Any]]
    ) -> bool:
        """벡터 검색 결과 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.VECTOR_RESULTS.format(
                query_hash=query_hash,
                collection=collection
            )
            
            await self.cache.cache_set(key, results, ttl=self.ttl.VECTOR_RESULTS)
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("벡터 결과 캐시 저장 실패", error=str(e))
            return False
    
    # === 메타데이터 캐시 ===
    
    async def cache_email_metadata_get(self, email_id: str) -> Optional[Dict[str, Any]]:
        """이메일 메타데이터 캐시 조회"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.EMAIL_METADATA.format(email_id=email_id)
            return await self.cache.cache_get(key)
        except Exception as e:
            logger.error("이메일 메타데이터 캐시 조회 실패", error=str(e))
            return None
    
    async def cache_email_metadata_set(
        self,
        email_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """이메일 메타데이터 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.EMAIL_METADATA.format(email_id=email_id)
            await self.cache.cache_set(key, metadata, ttl=self.ttl.EMAIL_METADATA)
            return True
        except Exception as e:
            logger.error("이메일 메타데이터 캐시 저장 실패", error=str(e))
            return False
    
    async def cache_document_metadata_get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """문서 메타데이터 캐시 조회"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.DOCUMENT_METADATA.format(doc_id=doc_id)
            return await self.cache.cache_get(key)
        except Exception as e:
            logger.error("문서 메타데이터 캐시 조회 실패", error=str(e))
            return None
    
    async def cache_document_metadata_set(
        self,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """문서 메타데이터 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.DOCUMENT_METADATA.format(doc_id=doc_id)
            await self.cache.cache_set(key, metadata, ttl=self.ttl.DOCUMENT_METADATA)
            return True
        except Exception as e:
            logger.error("문서 메타데이터 캐시 저장 실패", error=str(e))
            return False
    
    # === 성능 메트릭 캐시 ===
    
    async def cache_performance_metric(
        self,
        operation: str,
        metric_data: Dict[str, Any]
    ) -> bool:
        """성능 메트릭 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H')
            key = self.keys.PERFORMANCE_METRICS.format(
                operation=operation,
                timestamp=timestamp
            )
            
            await self.cache.cache_set(key, metric_data, ttl=self.ttl.PERFORMANCE_METRICS)
            return True
        except Exception as e:
            logger.error("성능 메트릭 캐시 저장 실패", error=str(e))
            return False
    
    # === 최근 검색 캐시 ===
    
    async def cache_recent_search(
        self,
        user_id: str,
        query_id: str,
        search_data: Dict[str, Any]
    ) -> bool:
        """최근 검색 캐시 저장"""
        await self._ensure_initialized()
        
        try:
            key = self.keys.RECENT_SEARCHES.format(
                user_id=user_id or "anonymous",
                query_id=query_id
            )
            
            await self.cache.cache_set(key, search_data, ttl=self.ttl.RECENT_SEARCHES)
            return True
        except Exception as e:
            logger.error("최근 검색 캐시 저장 실패", error=str(e))
            return False
    
    # === 범용 캐시 메서드 ===
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """범용 캐시 조회 (search 모듈 내부용)"""
        await self._ensure_initialized()
        
        try:
            # search: 프리픽스 확인
            if not key.startswith("search:"):
                logger.warning("잘못된 캐시 키 형식", key=key)
                return None
            
            return await self.cache.cache_get(key)
        except Exception as e:
            logger.error("캐시 조회 실패", key=key, error=str(e))
            return None
    
    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """범용 캐시 저장 (search 모듈 내부용)"""
        await self._ensure_initialized()
        
        try:
            # search: 프리픽스 확인
            if not key.startswith("search:"):
                logger.warning("잘못된 캐시 키 형식", key=key)
                return False
            
            # 기본 TTL 설정
            if ttl is None:
                ttl = 600  # 기본 10분
            
            await self.cache.cache_set(key, value, ttl)
            return True
        except Exception as e:
            logger.error("캐시 저장 실패", key=key, error=str(e))
            return False
    
    # === 통계 및 관리 ===
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "errors": self._stats["errors"],
            "hit_rate": hit_rate,
            "total_requests": total
        }
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """패턴 기반 캐시 무효화
        
        Args:
            pattern: 무효화할 캐시 키 패턴 (예: "search:embedding:*")
            
        Returns:
            무효화된 키 개수
        """
        await self._ensure_initialized()
        
        # 실제 구현에서는 Redis SCAN과 DEL을 사용
        # 여기서는 간단한 시뮬레이션
        logger.info("캐시 패턴 무효화", pattern=pattern)
        return 0
    
    # === 내부 헬퍼 함수 ===
    
    def _generate_text_hash(self, text: str) -> str:
        """텍스트 해시 생성 (임베딩용)"""
        normalized = text.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _generate_query_hash(self, query: str) -> str:
        """쿼리 해시 생성 (처리된 쿼리용)"""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def _generate_result_hash(self, results: List[Any]) -> str:
        """결과 해시 생성 (결과 캐싱용)"""
        # 결과 목록의 ID들로 해시 생성
        result_ids = [str(r.get("id", "")) for r in results[:10]]  # 상위 10개만
        combined = "".join(result_ids)
        return hashlib.md5(combined.encode()).hexdigest()[:16]


# 싱글톤 인스턴스
_search_cache_manager = None


async def get_search_cache_manager() -> SearchCacheManager:
    """Search 캐시 관리자 싱글톤 인스턴스 반환"""
    global _search_cache_manager
    
    if _search_cache_manager is None:
        _search_cache_manager = SearchCacheManager()
        await _search_cache_manager._ensure_initialized()
    
    return _search_cache_manager
