"""
IACSRAG MongoDB 연결 및 세션 관리

Motor를 사용한 비동기 MongoDB 클라이언트 관리
infra/core 아키텍쳐 지침: 연결, 초기화, 설정만 담당
"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# 전역 MongoDB 클라이언트 인스턴스
_mongodb_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongodb() -> None:
    """MongoDB에 연결합니다."""
    global _mongodb_client, _database
    
    try:
        logger.info("MongoDB 연결을 시작합니다", url=settings.mongodb_url)
        
        _mongodb_client = AsyncIOMotorClient(
            settings.mongodb_url,
            minPoolSize=settings.mongodb_min_pool_size,
            maxPoolSize=settings.mongodb_max_pool_size,
            serverSelectionTimeoutMS=5000,  # 5초 타임아웃
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )
        
        # 연결 테스트
        await _mongodb_client.admin.command('ping')
        
        _database = _mongodb_client[settings.mongodb_database]
        
        logger.info(
            "MongoDB 연결이 성공했습니다",
            database=settings.mongodb_database,
            min_pool_size=settings.mongodb_min_pool_size,
            max_pool_size=settings.mongodb_max_pool_size
        )
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error("MongoDB 연결에 실패했습니다", error=str(e))
        raise
    except Exception as e:
        logger.error("MongoDB 초기화 중 예상치 못한 오류가 발생했습니다", error=str(e))
        raise


async def disconnect_from_mongodb() -> None:
    """MongoDB 연결을 해제합니다."""
    global _mongodb_client, _database
    
    if _mongodb_client:
        logger.info("MongoDB 연결을 해제합니다")
        _mongodb_client.close()
        _mongodb_client = None
        _database = None
        logger.info("MongoDB 연결이 해제되었습니다")


def get_mongodb_client() -> AsyncIOMotorClient:
    """MongoDB 클라이언트를 반환합니다."""
    if not _mongodb_client:
        raise RuntimeError("MongoDB 클라이언트가 초기화되지 않았습니다. connect_to_mongodb()를 먼저 호출하세요.")
    return _mongodb_client


def get_database() -> AsyncIOMotorDatabase:
    """현재 데이터베이스를 반환합니다."""
    if not _database:
        raise RuntimeError("데이터베이스가 초기화되지 않았습니다. connect_to_mongodb()를 먼저 호출하세요.")
    return _database


# 애플리케이션 시작/종료 시 호출할 함수들
startup_handler = connect_to_mongodb
shutdown_handler = disconnect_from_mongodb
