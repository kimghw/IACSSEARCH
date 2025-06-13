"""
IACSRAG Qdrant 벡터 저장소 연결 및 작업 관리

Qdrant 클라이언트 연결, 세션 관리 및 기본적인 벡터 작업 제공
infra 아키텍쳐 지침: 연결, 초기화, 설정 및 공통 벡터 작업 담당
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, Match, Range
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
import openai
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# 전역 클라이언트 인스턴스들
_qdrant_client: Optional[QdrantClient] = None
_openai_client: Optional[openai.AsyncOpenAI] = None


@dataclass
class VectorMatch:
    """벡터 검색 결과"""
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None


@dataclass
class SearchFilters:
    """통합 검색 필터 - Qdrant와 MongoDB 모두 지원"""
    # 공통 필드들 (양쪽 모두 지원)
    document_id: Optional[str] = None  # MongoDB: id, Qdrant: document_id
    subjectprefix: Optional[str] = None
    sender_name: Optional[str] = None
    sender_address: Optional[str] = None
    has_attachments: Optional[bool] = None
    thread_id: Optional[str] = None
    
    # 날짜 필터 (유연한 타입 지원)
    received_date_start: Optional[str] = None  # "2024-01-01" 형태
    received_date_end: Optional[str] = None    # "2024-12-31" 형태
    
    # Qdrant 전용 필드들
    issue_tags: Optional[List[str]] = None
    processing_status: Optional[str] = None
    
    # MongoDB 전용 필드들 (추후 확장시 사용)
    graph_email_id: Optional[str] = None
    processed_at_start: Optional[str] = None
    processed_at_end: Optional[str] = None


async def connect_to_qdrant() -> None:
    """Qdrant 벡터 데이터베이스에 연결합니다."""
    global _qdrant_client
    
    try:
        logger.info("Qdrant 연결을 시작합니다", url=settings.qdrant_url)
        
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            timeout=30,
            prefer_grpc=False,  # HTTP API 사용
            check_compatibility=False  # 버전 호환성 체크 비활성화
        )
        
        # 연결 테스트 - 컬렉션 목록 조회로 대체
        try:
            collections = _qdrant_client.get_collections()
            logger.info(
                "Qdrant 연결이 성공했습니다",
                collections_count=len(collections.collections) if collections else 0
            )
        except Exception as e:
            logger.warning(f"Qdrant 컬렉션 목록 조회 실패: {e}")
            # 연결은 성공했지만 컬렉션이 없을 수 있음
            logger.info("Qdrant 연결이 성공했습니다 (컬렉션 없음)")
        
    except (ResponseHandlingException, UnexpectedResponse) as e:
        logger.error("Qdrant 연결에 실패했습니다", error=str(e))
        raise
    except Exception as e:
        logger.error("Qdrant 초기화 중 예상치 못한 오류가 발생했습니다", error=str(e))
        raise


async def connect_to_openai() -> None:
    """OpenAI API 클라이언트를 초기화합니다."""
    global _openai_client
    
    try:
        logger.info("OpenAI API 클라이언트를 초기화합니다")
        
        if not settings.openai_api_key:
            logger.warning("OpenAI API 키가 설정되지 않았습니다")
            return
            
        _openai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0
        )
        
        logger.info("OpenAI API 클라이언트 초기화가 완료되었습니다")
        
    except Exception as e:
        logger.error("OpenAI API 클라이언트 초기화 중 오류가 발생했습니다", error=str(e))
        raise


async def disconnect_from_qdrant() -> None:
    """Qdrant 연결을 해제합니다."""
    global _qdrant_client
    
    if _qdrant_client:
        logger.info("Qdrant 연결을 해제합니다")
        _qdrant_client.close()
        _qdrant_client = None
        logger.info("Qdrant 연결이 해제되었습니다")


async def disconnect_from_openai() -> None:
    """OpenAI 클라이언트를 해제합니다."""
    global _openai_client
    
    if _openai_client:
        logger.info("OpenAI 클라이언트를 해제합니다")
        await _openai_client.close()
        _openai_client = None
        logger.info("OpenAI 클라이언트가 해제되었습니다")


def get_qdrant_client() -> QdrantClient:
    """Qdrant 클라이언트를 반환합니다."""
    if not _qdrant_client:
        raise RuntimeError("Qdrant 클라이언트가 초기화되지 않았습니다. connect_to_qdrant()를 먼저 호출하세요.")
    return _qdrant_client


def get_openai_client() -> openai.AsyncOpenAI:
    """OpenAI 클라이언트를 반환합니다."""
    if not _openai_client:
        raise RuntimeError("OpenAI 클라이언트가 초기화되지 않았습니다. connect_to_openai()를 먼저 호출하세요.")
    return _openai_client


class VectorStoreManager:
    """벡터 저장소 작업 관리자 - 싱글톤 패턴 + 지연 초기화"""
    
    _instance: Optional['VectorStoreManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.collection_name = settings.qdrant_collection_name
            self.vector_size = settings.qdrant_vector_size
            self.similarity_threshold = settings.search_similarity_threshold
            self._auto_initialize()
            VectorStoreManager._initialized = True
    
    def _auto_initialize(self):
        """필요시 자동으로 연결 초기화"""
        # VectorStoreManager는 싱글톤이므로 자동 초기화는 하지 않음
        # 대신 SearchOrchestrator에서 명시적으로 초기화
        logger.debug("VectorStoreManager 인스턴스 생성됨 (자동 초기화 비활성화)")
    
    @property
    def qdrant_client(self) -> QdrantClient:
        """Qdrant 클라이언트 반환"""
        return get_qdrant_client()
    
    @property
    def openai_client(self) -> openai.AsyncOpenAI:
        """OpenAI 클라이언트 반환"""
        return get_openai_client()
    
    async def create_embedding(self, text: str) -> List[float]:
        """텍스트를 벡터로 변환"""
        try:
            logger.debug("임베딩 생성 시작", text_length=len(text))
            
            # 텍스트 길이 체크
            if len(text.strip()) == 0:
                raise ValueError("빈 텍스트로는 임베딩을 생성할 수 없습니다")
            
            # OpenAI API 호출
            response = await self.openai_client.embeddings.create(
                model=settings.openai_model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(
                "임베딩 생성 완료",
                embedding_dimension=len(embedding),
                model=settings.openai_model
            )
            
            return embedding
            
        except Exception as e:
            logger.error("임베딩 생성 중 오류 발생", error=str(e), text_preview=text[:100])
            raise
    
    async def search_vectors(
        self, 
        query_vector: List[float], 
        collection: Optional[str] = None,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        score_threshold: Optional[float] = None
    ) -> List[VectorMatch]:
        """벡터 유사도 검색"""
        try:
            collection = collection or self.collection_name
            score_threshold = score_threshold or self.similarity_threshold
            
            logger.debug(
                "벡터 검색 시작",
                collection=collection,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # 필터 생성
            qdrant_filter = None
            if filters:
                qdrant_filter = self._build_qdrant_filter(filters)
            
            # Qdrant 검색 실행
            # email_vectors 컬렉션은 named vectors를 사용하므로 vector_name 지정 필요
            if collection == "email_vectors":
                # body 벡터로 검색 (기본값)
                search_result = self.qdrant_client.search(
                    collection_name=collection,
                    query_vector=("body", query_vector),  # named vector 지정
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False
                )
            else:
                # 일반 컬렉션은 unnamed vector 사용
                search_result = self.qdrant_client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False
                )
            
            # 결과 변환
            matches = []
            for point in search_result:
                matches.append(VectorMatch(
                    id=str(point.id),
                    score=point.score,
                    payload=point.payload or {}
                ))
            
            logger.debug(
                "벡터 검색 완료",
                result_count=len(matches),
                top_score=matches[0].score if matches else 0
            )
            
            return matches
            
        except Exception as e:
            logger.error("벡터 검색 중 오류 발생", error=str(e))
            raise
    
    async def store_vector(
        self,
        vector: List[float],
        payload: Dict[str, Any],
        point_id: Optional[str] = None,
        collection: Optional[str] = None
    ) -> str:
        """벡터 저장"""
        try:
            collection = collection or self.collection_name
            
            logger.debug("벡터 저장 시작", collection=collection)
            
            # 포인트 ID 생성 (미제공 시)
            if not point_id:
                point_id = str(hash(str(vector[:10])))  # 간단한 ID 생성
            
            # Qdrant에 저장
            self.qdrant_client.upsert(
                collection_name=collection,
                points=[{
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                }]
            )
            
            logger.debug("벡터 저장 완료", point_id=point_id)
            
            return point_id
            
        except Exception as e:
            logger.error("벡터 저장 중 오류 발생", error=str(e))
            raise
    
    def _build_qdrant_filter(self, filters: SearchFilters) -> Filter:
        """SearchFilters를 Qdrant Filter로 변환"""
        conditions = []
        
        # 문서 ID 필터
        if filters.document_id:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=Match(value=filters.document_id)
                )
            )
        
        # 제목 프리픽스 필터
        if filters.subjectprefix:
            conditions.append(
                FieldCondition(
                    key="subjectprefix",
                    match=Match(value=filters.subjectprefix)
                )
            )
        
        # 발신자 이름 필터
        if filters.sender_name:
            conditions.append(
                FieldCondition(
                    key="sender_name",
                    match=Match(value=filters.sender_name)
                )
            )
        
        # 발신자 주소 필터
        if filters.sender_address:
            conditions.append(
                FieldCondition(
                    key="sender_address",
                    match=Match(value=filters.sender_address)
                )
            )
        
        # 날짜 범위 필터
        if filters.received_date_start and filters.received_date_end:
            conditions.append(
                FieldCondition(
                    key="received_date",
                    range=Range(
                        gte=filters.received_date_start,
                        lte=filters.received_date_end
                    )
                )
            )
        elif filters.received_date_start:
            conditions.append(
                FieldCondition(
                    key="received_date",
                    range=Range(gte=filters.received_date_start)
                )
            )
        elif filters.received_date_end:
            conditions.append(
                FieldCondition(
                    key="received_date",
                    range=Range(lte=filters.received_date_end)
                )
            )
        
        # 첨부파일 필터
        if filters.has_attachments is not None:
            conditions.append(
                FieldCondition(
                    key="has_attachments",
                    match=Match(value=filters.has_attachments)
                )
            )
        
        # 스레드 ID 필터
        if filters.thread_id:
            conditions.append(
                FieldCondition(
                    key="thread_id",
                    match=Match(value=filters.thread_id)
                )
            )
        
        # 이슈 태그 필터
        if filters.issue_tags:
            conditions.append(
                FieldCondition(
                    key="issue_tags",
                    match=Match(any=filters.issue_tags)
                )
            )
        
        # 처리 상태 필터
        if filters.processing_status:
            conditions.append(
                FieldCondition(
                    key="processing_status",
                    match=Match(value=filters.processing_status)
                )
            )
        
        return Filter(must=conditions) if conditions else None
    
    async def get_collection_info(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        try:
            collection = collection or self.collection_name
            
            logger.debug("컬렉션 정보 조회", collection=collection)
            
            collection_info = self.qdrant_client.get_collection(collection)
            
            return {
                "name": collection,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "status": collection_info.status,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value
                }
            }
            
        except Exception as e:
            logger.error("컬렉션 정보 조회 중 오류 발생", error=str(e))
            raise


# 전역 매니저 인스턴스
def get_vector_manager() -> VectorStoreManager:
    """벡터 매니저 인스턴스 반환 - 싱글톤 패턴"""
    return VectorStoreManager()


# 애플리케이션 시작/종료 시 호출할 함수들
async def startup_handler():
    """시작 시 모든 연결 초기화"""
    await connect_to_qdrant()
    await connect_to_openai()


async def shutdown_handler():
    """종료 시 모든 연결 해제"""
    await disconnect_from_qdrant()
    await disconnect_from_openai()
