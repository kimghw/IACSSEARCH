"""
IACSRAG Qdrant 벡터 저장소 연결 관리

Qdrant 클라이언트 연결 및 세션 관리
infra/core 아키텍쳐 지침: 연결, 초기화, 설정만 담당
"""

from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# 전역 Qdrant 클라이언트 인스턴스
_qdrant_client: Optional[QdrantClient] = None


async def connect_to_qdrant() -> None:
    """Qdrant 벡터 데이터베이스에 연결합니다."""
    global _qdrant_client
    
    try:
        logger.info("Qdrant 연결을 시작합니다", url=settings.qdrant_url)
        
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            timeout=30,
            prefer_grpc=False,  # HTTP API 사용
        )
        
        # 연결 테스트
        health_info = _qdrant_client.get_cluster_info()
        
        logger.info(
            "Qdrant 연결이 성공했습니다",
            cluster_info=health_info
        )
        
    except (ResponseHandlingException, UnexpectedResponse) as e:
        logger.error("Qdrant 연결에 실패했습니다", error=str(e))
        raise
    except Exception as e:
        logger.error("Qdrant 초기화 중 예상치 못한 오류가 발생했습니다", error=str(e))
        raise


async def disconnect_from_qdrant() -> None:
    """Qdrant 연결을 해제합니다."""
    global _qdrant_client
    
    if _qdrant_client:
        logger.info("Qdrant 연결을 해제합니다")
        _qdrant_client.close()
        _qdrant_client = None
        logger.info("Qdrant 연결이 해제되었습니다")


def get_qdrant_client() -> QdrantClient:
    """Qdrant 클라이언트를 반환합니다."""
    if not _qdrant_client:
        raise RuntimeError("Qdrant 클라이언트가 초기화되지 않았습니다. connect_to_qdrant()를 먼저 호출하세요.")
    return _qdrant_client


# 애플리케이션 시작/종료 시 호출할 함수들
startup_handler = connect_to_qdrant
shutdown_handler = disconnect_from_qdrant
