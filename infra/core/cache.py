"""
Redis 캐시 관리 모듈 (message_broker.py 대체)
개발 단계에서 간단한 캐싱 기능을 제공합니다.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import redis.asyncio as redis
from pydantic import BaseModel

from .config import get_settings

logger = logging.getLogger(__name__)


class CacheKey:
    """캐시 키 관리 클래스"""
    
    # 이메일 관련 캐시 키
    EMAIL_PROCESSING_STATUS = "email:processing:{email_id}"
    EMAIL_EMBEDDING_CACHE = "email:embedding:{email_id}"
    
    # 스레드 관련 캐시 키
    THREAD_STATUS_CACHE = "thread:status:{thread_id}"
    THREAD_PARTICIPANTS = "thread:participants:{thread_id}"
    
    # 참여자 관련 캐시 키
    PARTICIPANT_STATUS = "participant:status:{email}:{thread_id}"
    PARTICIPANT_ROLE_MAPPING = "participant:role:{email}"
    
    # 마감일 관련 캐시 키
    DEADLINE_NOTIFICATIONS = "deadline:notifications:{thread_id}"
    OVERDUE_PARTICIPANTS = "deadline:overdue"
    
    # 이슈 분석 관련 캐시 키
    ISSUE_TAGS_CACHE = "issue:tags:{email_id}"
    SIMILAR_ISSUES_CACHE = "issue:similar:{vector_id}"
    
    # 대시보드 관련 캐시 키
    DASHBOARD_STATS = "dashboard:stats:{user_id}"
    SEARCH_RESULTS_CACHE = "search:results:{query_hash}"


class CacheService:
    """Redis 캐시 서비스 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = 3600  # 1시간 기본 TTL
        
    async def connect(self) -> None:
        """Redis 연결 초기화"""
        try:
            # Redis URL 파싱하여 연결 설정 생성
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                password=self.settings.redis_password,
                db=self.settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=self.settings.redis_max_connections
            )
            
            # 연결 테스트
            await self.redis_client.ping()
            logger.info("Redis 캐시 서비스 연결 성공")
            
        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")
            self.redis_client = None
            
    async def disconnect(self) -> None:
        """Redis 연결 해제"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis 캐시 서비스 연결 해제")
            
    async def is_connected(self) -> bool:
        """Redis 연결 상태 확인"""
        if not self.redis_client:
            return False
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    # === 기본 캐시 작업 메서드 ===
    
    async def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시 데이터 저장"""
        if not self.redis_client:
            logger.warning(f"Redis 연결이 없어 캐시 저장 실패: {key}")
            return False
            
        try:
            if isinstance(value, (dict, list, BaseModel)):
                if isinstance(value, BaseModel):
                    value = value.model_dump()
                value = json.dumps(value, ensure_ascii=False, default=str)
            
            ttl = ttl or self.default_ttl
            await self.redis_client.setex(key, ttl, value)
            logger.debug(f"캐시 저장 성공: {key}")
            return True
            
        except Exception as e:
            logger.error(f"캐시 저장 실패 {key}: {e}")
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """캐시 데이터 조회"""
        if not self.redis_client:
            logger.warning(f"Redis 연결이 없어 캐시 조회 실패: {key}")
            return None
            
        try:
            value = await self.redis_client.get(key)
            if value is None:
                return None
                
            # JSON 파싱 시도
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error(f"캐시 조회 실패 {key}: {e}")
            return None
    
    async def cache_delete(self, key: str) -> bool:
        """캐시 데이터 삭제"""
        if not self.redis_client:
            return False
            
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 삭제 실패 {key}: {e}")
            return False
    
    async def cache_exists(self, key: str) -> bool:
        """캐시 키 존재 여부 확인"""
        if not self.redis_client:
            return False
            
        try:
            result = await self.redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 존재 확인 실패 {key}: {e}")
            return False
    
    # === 이메일 처리 상태 관리 ===
    
    async def cache_set_email_processing_status(self, email_id: str, status: str, ttl: int = 3600) -> bool:
        """이메일 처리 상태 캐시 저장"""
        key = CacheKey.EMAIL_PROCESSING_STATUS.format(email_id=email_id)
        status_data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "email_id": email_id
        }
        return await self.cache_set(key, status_data, ttl)
    
    async def cache_get_email_processing_status(self, email_id: str) -> Optional[Dict[str, Any]]:
        """이메일 처리 상태 캐시 조회"""
        key = CacheKey.EMAIL_PROCESSING_STATUS.format(email_id=email_id)
        return await self.cache_get(key)
    
    async def cache_set_email_embedding(self, email_id: str, embedding: List[float], ttl: int = 86400) -> bool:
        """이메일 임베딩 캐시 저장 (24시간)"""
        key = CacheKey.EMAIL_EMBEDDING_CACHE.format(email_id=email_id)
        embedding_data = {
            "embedding": embedding,
            "timestamp": datetime.now().isoformat(),
            "email_id": email_id
        }
        return await self.cache_set(key, embedding_data, ttl)
    
    async def cache_get_email_embedding(self, email_id: str) -> Optional[List[float]]:
        """이메일 임베딩 캐시 조회"""
        key = CacheKey.EMAIL_EMBEDDING_CACHE.format(email_id=email_id)
        data = await self.cache_get(key)
        return data.get("embedding") if data else None
    
    # === 스레드 상태 관리 ===
    
    async def cache_set_thread_status(self, thread_id: str, status: str, ttl: int = 7200) -> bool:
        """스레드 상태 캐시 저장"""
        key = CacheKey.THREAD_STATUS_CACHE.format(thread_id=thread_id)
        status_data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "thread_id": thread_id
        }
        return await self.cache_set(key, status_data, ttl)
    
    async def cache_get_thread_status(self, thread_id: str) -> Optional[str]:
        """스레드 상태 캐시 조회"""
        key = CacheKey.THREAD_STATUS_CACHE.format(thread_id=thread_id)
        data = await self.cache_get(key)
        return data.get("status") if data else None
    
    # === 참여자 상태 관리 ===
    
    async def cache_set_participant_status(self, email: str, thread_id: str, status: str, ttl: int = 3600) -> bool:
        """참여자 상태 캐시 저장"""
        key = CacheKey.PARTICIPANT_STATUS.format(email=email, thread_id=thread_id)
        status_data = {
            "status": status,
            "email": email,
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat()
        }
        return await self.cache_set(key, status_data, ttl)
    
    async def cache_get_participant_status(self, email: str, thread_id: str) -> Optional[str]:
        """참여자 상태 캐시 조회"""
        key = CacheKey.PARTICIPANT_STATUS.format(email=email, thread_id=thread_id)
        data = await self.cache_get(key)
        return data.get("status") if data else None
    
    # === 검색 결과 캐시 ===
    
    async def cache_set_search_results(self, query_hash: str, results: List[Dict], ttl: int = 1800) -> bool:
        """검색 결과 캐시 저장 (30분)"""
        key = CacheKey.SEARCH_RESULTS_CACHE.format(query_hash=query_hash)
        search_data = {
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "query_hash": query_hash
        }
        return await self.cache_set(key, search_data, ttl)
    
    async def cache_get_search_results(self, query_hash: str) -> Optional[List[Dict]]:
        """검색 결과 캐시 조회"""
        key = CacheKey.SEARCH_RESULTS_CACHE.format(query_hash=query_hash)
        data = await self.cache_get(key)
        return data.get("results") if data else None
    
    # === 대시보드 통계 캐시 ===
    
    async def cache_set_dashboard_stats(self, user_id: str, stats: Dict, ttl: int = 600) -> bool:
        """대시보드 통계 캐시 저장 (10분)"""
        key = CacheKey.DASHBOARD_STATS.format(user_id=user_id)
        return await self.cache_set(key, stats, ttl)
    
    async def cache_get_dashboard_stats(self, user_id: str) -> Optional[Dict]:
        """대시보드 통계 캐시 조회"""
        key = CacheKey.DASHBOARD_STATS.format(user_id=user_id)
        return await self.cache_get(key)
    
    # === 헬스체크 ===
    
    async def health_check(self) -> Dict[str, Any]:
        """캐시 서비스 헬스체크"""
        try:
            if not self.redis_client:
                return {"status": "unhealthy", "error": "Redis client not initialized"}
            
            start_time = datetime.now()
            await self.redis_client.ping()
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Redis 정보 조회
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown")
            }
            
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# 전역 캐시 서비스 인스턴스
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """캐시 서비스 인스턴스 반환 (싱글톤)"""
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    
    return _cache_service


async def cleanup_cache_service() -> None:
    """캐시 서비스 정리"""
    global _cache_service
    
    if _cache_service:
        await _cache_service.disconnect()
        _cache_service = None
