"""
IACSRAG MongoDB 연결 및 세션 관리

레이지 싱글톤 패턴으로 리팩토링됨 - 하위 호환성 유지
infra/core 아키텍쳐 지침: 연결, 초기화, 설정만 담당
"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import structlog

from .core import get_database_manager

logger = structlog.get_logger(__name__)


async def connect_to_mongodb() -> None:
    """MongoDB에 연결합니다. (하위 호환성 - 내부적으로 DatabaseManager 사용)"""
    db_manager = get_database_manager()
    await db_manager.ensure_initialized()
    logger.info("MongoDB 연결 완료 (DatabaseManager 사용)")


async def disconnect_from_mongodb() -> None:
    """MongoDB 연결을 해제합니다. (하위 호환성 - 내부적으로 DatabaseManager 사용)"""
    db_manager = get_database_manager()
    await db_manager.disconnect()
    logger.info("MongoDB 연결 해제 완료 (DatabaseManager 사용)")


def get_mongodb_client() -> AsyncIOMotorClient:
    """MongoDB 클라이언트를 반환합니다. (하위 호환성 - 내부적으로 DatabaseManager 사용)"""
    db_manager = get_database_manager()
    if not db_manager.client:
        raise RuntimeError("MongoDB 클라이언트가 초기화되지 않았습니다. connect_to_mongodb()를 먼저 호출하세요.")
    return db_manager.client


def get_database() -> AsyncIOMotorDatabase:
    """현재 데이터베이스를 반환합니다. (하위 호환성 - 내부적으로 DatabaseManager 사용)"""
    db_manager = get_database_manager()
    return db_manager.get_database()


# 애플리케이션 시작/종료 시 호출할 함수들 (하위 호환성)
startup_handler = connect_to_mongodb
shutdown_handler = disconnect_from_mongodb
