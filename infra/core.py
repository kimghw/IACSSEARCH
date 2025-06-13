"""
인프라 코어 - 모든 외부 서비스 연결을 관리하는 레이지 싱글톤 매니저

레이지 싱글톤 패턴을 사용하여 필요한 시점에만 연결을 초기화하고
애플리케이션 전체에서 단일 인스턴스를 공유합니다.
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from qdrant_client import QdrantClient
import openai
import redis.asyncio as redis

from .config import get_settings

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """MongoDB 연결 관리자 - 레이지 싱글톤"""
    
    _instance: Optional['DatabaseManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_init_done'):
            self.client: Optional[AsyncIOMotorClient] = None
            self.database: Optional[AsyncIOMotorDatabase] = None
            self._init_done = True
            self._lock = asyncio.Lock()
    
    async def ensure_initialized(self) -> None:
        """레이지 초기화 - 필요할 때만 연결"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:  # Double-check
                return
                
            await self._connect()
            self._initialized = True
    
    async def _connect(self) -> None:
        """실제 MongoDB 연결"""
        settings = get_settings()
        
        try:
            logger.info("MongoDB 연결 시작", url=settings.mongodb_url)
            
            self.client = AsyncIOMotorClient(
                settings.mongodb_url,
                minPoolSize=settings.mongodb_min_pool_size,
                maxPoolSize=settings.mongodb_max_pool_size,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
            )
            
            # 연결 테스트
            await self.client.admin.command('ping')
            self.database = self.client[settings.mongodb_database]
            
            logger.info("MongoDB 연결 성공", database=settings.mongodb_database)
            
        except Exception as e:
            logger.error("MongoDB 연결 실패", error=str(e))
            self._initialized = False
            raise
    
    async def disconnect(self) -> None:
        """연결 해제"""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self._initialized = False
            logger.info("MongoDB 연결 해제")
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """MongoDB 데이터베이스 객체 반환"""
        if not self._initialized or self.database is None:
            raise RuntimeError("DatabaseManager가 초기화되지 않았습니다")
        return self.database


class VectorStoreManager:
    """벡터 저장소 관리자 - 레이지 싱글톤"""
    
    _instance: Optional['VectorStoreManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_init_done'):
            self.qdrant_client: Optional[QdrantClient] = None
            self.openai_client: Optional[openai.AsyncOpenAI] = None
            self._init_done = True
            self._lock = asyncio.Lock()
    
    async def ensure_initialized(self) -> None:
        """레이지 초기화"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            await self._connect()
            self._initialized = True
    
    async def _connect(self) -> None:
        """Qdrant 및 OpenAI 연결"""
        settings = get_settings()
        
        # Qdrant 연결
        try:
            logger.info("Qdrant 연결 시작", url=settings.qdrant_url)
            
            self.qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                timeout=30,
                prefer_grpc=False,
                check_compatibility=False
            )
            
            # 연결 테스트
            collections = self.qdrant_client.get_collections()
            logger.info("Qdrant 연결 성공", collections_count=len(collections.collections))
            
        except Exception as e:
            logger.error("Qdrant 연결 실패", error=str(e))
            raise
        
        # OpenAI 초기화
        if settings.openai_api_key:
            try:
                logger.info("OpenAI 클라이언트 초기화")
                self.openai_client = openai.AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    timeout=30.0
                )
                logger.info("OpenAI 클라이언트 초기화 성공")
            except Exception as e:
                logger.error("OpenAI 초기화 실패", error=str(e))
                # OpenAI 실패는 치명적이지 않음
        else:
            logger.warning("OpenAI API 키가 설정되지 않음")
    
    async def disconnect(self) -> None:
        """연결 해제"""
        if self.qdrant_client:
            self.qdrant_client.close()
            self.qdrant_client = None
        
        if self.openai_client:
            await self.openai_client.close()
            self.openai_client = None
        
        self._initialized = False
        logger.info("VectorStore 연결 해제")
    
    async def create_embedding(self, text: str) -> list[float]:
        """텍스트를 임베딩으로 변환"""
        if not self.openai_client:
            raise RuntimeError("OpenAI 클라이언트가 초기화되지 않았습니다")
        
        response = await self.openai_client.embeddings.create(
            model=get_settings().openai_model,
            input=text,
            encoding_format="float"
        )
        
        return response.data[0].embedding


class CacheManager:
    """캐시 관리자 - 레이지 싱글톤"""
    
    _instance: Optional['CacheManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_init_done'):
            self.redis_client: Optional[redis.Redis] = None
            self._init_done = True
            self._lock = asyncio.Lock()
            self.default_ttl = 3600
    
    async def ensure_initialized(self) -> None:
        """레이지 초기화"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            await self._connect()
            self._initialized = True
    
    async def _connect(self) -> None:
        """Redis 연결"""
        settings = get_settings()
        
        try:
            logger.info("Redis 연결 시작")
            
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=settings.redis_max_connections
            )
            
            # 연결 테스트
            await self.redis_client.ping()
            logger.info("Redis 연결 성공")
            
        except Exception as e:
            logger.error("Redis 연결 실패", error=str(e))
            # Redis 실패는 치명적이지 않음 - 캐시 없이 동작 가능
            self.redis_client = None
    
    async def disconnect(self) -> None:
        """연결 해제"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self._initialized = False
            logger.info("Redis 연결 해제")
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        if not self.redis_client:
            return None
            
        try:
            import json
            value = await self.redis_client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error("캐시 조회 실패", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시 저장"""
        if not self.redis_client:
            return False
            
        try:
            import json
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            
            ttl = ttl or self.default_ttl
            await self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error("캐시 저장 실패", key=key, error=str(e))
            return False


class InfraCore:
    """모든 인프라 매니저를 통합 관리하는 코어 클래스"""
    
    _instance: Optional['InfraCore'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_init_done'):
            self.database = DatabaseManager()
            self.vector_store = VectorStoreManager()
            self.cache = CacheManager()
            self._init_done = True
            self._lock = asyncio.Lock()
            self._init_time: Optional[datetime] = None
    
    async def ensure_initialized(self) -> None:
        """모든 서비스 레이지 초기화"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
            
            start_time = datetime.now()
            logger.info("InfraCore 초기화 시작")
            
            # 병렬 초기화 시도
            tasks = [
                self.database.ensure_initialized(),
                self.vector_store.ensure_initialized(),
                self.cache.ensure_initialized()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 확인
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    service_name = ["Database", "VectorStore", "Cache"][i]
                    logger.error(f"{service_name} 초기화 실패", error=str(result))
                    # Database 실패는 치명적
                    if i == 0:
                        raise result
            
            self._initialized = True
            self._init_time = datetime.now()
            elapsed = (self._init_time - start_time).total_seconds()
            
            logger.info("InfraCore 초기화 완료", elapsed_seconds=elapsed)
    
    async def shutdown(self) -> None:
        """모든 연결 정리"""
        logger.info("InfraCore 종료 시작")
        
        await asyncio.gather(
            self.database.disconnect(),
            self.vector_store.disconnect(),
            self.cache.disconnect(),
            return_exceptions=True
        )
        
        self._initialized = False
        logger.info("InfraCore 종료 완료")
    
    async def health_check(self) -> Dict[str, Any]:
        """전체 헬스체크"""
        health = {
            "status": "healthy",
            "initialized": self._initialized,
            "init_time": self._init_time.isoformat() if self._init_time else None,
            "services": {}
        }
        
        # Database 체크
        try:
            await self.database.get_database().admin.command('ping')
            health["services"]["database"] = {"status": "healthy"}
        except Exception as e:
            health["services"]["database"] = {"status": "unhealthy", "error": str(e)}
            health["status"] = "degraded"
        
        # VectorStore 체크
        try:
            if self.vector_store.qdrant_client:
                self.vector_store.qdrant_client.get_collections()
                health["services"]["vector_store"] = {"status": "healthy"}
            else:
                health["services"]["vector_store"] = {"status": "not_initialized"}
        except Exception as e:
            health["services"]["vector_store"] = {"status": "unhealthy", "error": str(e)}
            health["status"] = "degraded"
        
        # Cache 체크
        try:
            if self.cache.redis_client:
                await self.cache.redis_client.ping()
                health["services"]["cache"] = {"status": "healthy"}
            else:
                health["services"]["cache"] = {"status": "not_initialized"}
        except Exception as e:
            health["services"]["cache"] = {"status": "unhealthy", "error": str(e)}
            # 캐시는 선택적이므로 전체 상태는 변경하지 않음
        
        return health


# 전역 싱글톤 인스턴스 접근 함수
def get_infra_core() -> InfraCore:
    """InfraCore 싱글톤 인스턴스 반환"""
    return InfraCore()


# 개별 매니저 접근 함수 (하위 호환성)
def get_database_manager() -> DatabaseManager:
    """DatabaseManager 싱글톤 인스턴스 반환"""
    return get_infra_core().database


def get_vector_store_manager() -> VectorStoreManager:
    """VectorStoreManager 싱글톤 인스턴스 반환"""
    return get_infra_core().vector_store


def get_cache_manager() -> CacheManager:
    """CacheManager 싱글톤 인스턴스 반환"""
    return get_infra_core().cache


# FastAPI 앱 시작/종료 핸들러
async def startup_handler():
    """애플리케이션 시작 시 호출"""
    core = get_infra_core()
    await core.ensure_initialized()


async def shutdown_handler():
    """애플리케이션 종료 시 호출"""
    core = get_infra_core()
    await core.shutdown()
