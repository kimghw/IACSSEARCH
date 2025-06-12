"""
IACSRAG 코어 인프라 모듈

데이터베이스 연결, 벡터 저장소, 캐시, 설정 관리 등 핵심 인프라 컴포넌트
"""

from .config import settings, get_settings
from .database import get_mongodb_client, get_database, startup_handler as db_startup, shutdown_handler as db_shutdown
from .vector_store import get_qdrant_client, startup_handler as qdrant_startup, shutdown_handler as qdrant_shutdown
from .cache import get_cache_service, cleanup_cache_service, CacheService, CacheKey
from .logging import setup_logging, get_logger

__all__ = [
    # 설정
    "settings",
    "get_settings",
    
    # 데이터베이스
    "get_mongodb_client", 
    "get_database",
    
    # 벡터 저장소
    "get_qdrant_client",
    
    # 캐시
    "get_cache_service",
    "cleanup_cache_service",
    "CacheService",
    "CacheKey",
    
    # 로깅
    "setup_logging",
    "get_logger",
    
    # 시작/종료 핸들러
    "db_startup",
    "db_shutdown", 
    "qdrant_startup",
    "qdrant_shutdown",
]
