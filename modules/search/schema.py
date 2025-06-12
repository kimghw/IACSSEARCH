"""Search 모듈 데이터 스키마 정의

Pydantic v2를 사용한 데이터 계약 정의
모든 검색 관련 요청/응답 모델 포함
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SearchMode(str, Enum):
    """검색 모드 정의
    
    HYBRID: 필터와 벡터 검색을 함께 사용 (기본값)
    VECTOR_ONLY: 순수 벡터 검색만 사용
    FILTER_ONLY: 필터 검색만 사용
    """
    HYBRID = "hybrid"
    VECTOR_ONLY = "vector_only"
    FILTER_ONLY = "filter_only"


class CollectionStrategy(str, Enum):
    """컬렉션 선택 전략
    
    SINGLE: 단일 컬렉션만 검색 (기본값)
    MULTIPLE: 여러 컬렉션 동시 검색
    AUTO: 질의 내용에 따라 자동 선택
    """
    SINGLE = "single"
    MULTIPLE = "multiple"
    AUTO = "auto"


class DateRange(BaseModel):
    """날짜 범위 필터"""
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """종료 날짜가 시작 날짜보다 늦은지 검증"""
        if v and info.data.get('start_date'):
            if v < info.data['start_date']:
                raise ValueError("종료 날짜는 시작 날짜보다 늦어야 합니다")
        return v


class SearchFilters(BaseModel):
    """검색 필터 옵션"""
    date_range: Optional[DateRange] = Field(None, description="날짜 범위 필터")
    sender: Optional[str] = Field(None, description="발신자 필터")
    recipients: Optional[List[str]] = Field(default_factory=list, description="수신자 목록 필터")
    subject_keywords: Optional[List[str]] = Field(default_factory=list, description="제목 키워드 필터")
    has_attachments: Optional[bool] = Field(None, description="첨부파일 유무 필터")
    email_type: Optional[str] = Field(None, description="이메일 유형 필터")
    tags: Optional[List[str]] = Field(default_factory=list, description="태그 필터")
    custom_filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="커스텀 필터")


class SearchQuery(BaseModel):
    """검색 요청 데이터"""
    query_text: str = Field(..., min_length=1, max_length=1000, description="검색 질의 텍스트")
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="검색 모드")
    collection_strategy: CollectionStrategy = Field(default=CollectionStrategy.SINGLE, description="컬렉션 선택 전략")
    target_collections: Optional[List[str]] = Field(None, description="검색할 컬렉션 목록")
    filters: Optional[SearchFilters] = Field(None, description="검색 필터")
    limit: int = Field(default=20, ge=1, le=100, description="결과 개수 제한")
    offset: int = Field(default=0, ge=0, description="결과 오프셋")
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="유사도 점수 임계값")
    include_metadata: bool = Field(default=True, description="메타데이터 포함 여부")
    highlight_query: bool = Field(default=True, description="검색어 하이라이팅 여부")
    
    @field_validator('query_text')
    @classmethod
    def validate_query_text(cls, v: str) -> str:
        """검색어 유효성 검증"""
        v = v.strip()
        if not v:
            raise ValueError("검색어는 공백만으로 구성될 수 없습니다")
        return v
    
    @field_validator('target_collections')
    @classmethod
    def validate_collections(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """컬렉션 목록 유효성 검증"""
        if v:
            # 중복 제거
            v = list(set(v))
            # 빈 문자열 제거
            v = [c for c in v if c.strip()]
            if not v:
                return None
        return v


class ProcessedQuery(BaseModel):
    """전처리된 질의 데이터"""
    original_text: str = Field(..., description="원본 질의 텍스트")
    normalized_text: str = Field(..., description="정규화된 질의 텍스트")
    extracted_filters: Optional[SearchFilters] = Field(None, description="추출된 필터")
    language: str = Field(default="ko", description="감지된 언어")
    query_type: str = Field(default="general", description="질의 유형")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    processing_metadata: Dict[str, Any] = Field(default_factory=dict, description="전처리 메타데이터")


class EmbeddingRequest(BaseModel):
    """임베딩 요청 데이터"""
    text: str = Field(..., description="임베딩할 텍스트")
    model: str = Field(default="text-embedding-ada-002", description="사용할 임베딩 모델")
    cache_key: Optional[str] = Field(None, description="캐시 키")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class VectorMatch(BaseModel):
    """벡터 검색 결과"""
    document_id: str = Field(..., description="문서 ID")
    score: float = Field(..., ge=0.0, le=1.0, description="유사도 점수")
    collection_name: str = Field(..., description="소속 컬렉션 이름")
    vector: Optional[List[float]] = Field(None, description="벡터 값")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")
    distance: Optional[float] = Field(None, description="벡터 거리")


class EnrichmentData(BaseModel):
    """메타데이터 보강 정보"""
    document_id: str = Field(..., description="문서 ID")
    title: Optional[str] = Field(None, description="문서 제목")
    content_snippet: Optional[str] = Field(None, description="내용 스니펫")
    highlighted_content: Optional[str] = Field(None, description="하이라이트된 내용")
    sender: Optional[str] = Field(None, description="발신자")
    recipients: Optional[List[str]] = Field(None, description="수신자 목록")
    date: Optional[datetime] = Field(None, description="날짜")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="첨부파일 정보")
    tags: Optional[List[str]] = Field(None, description="태그")
    additional_metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class SearchResult(BaseModel):
    """개별 검색 결과"""
    document_id: str = Field(..., description="문서 ID")
    score: float = Field(..., ge=0.0, le=1.0, description="관련성 점수")
    source_collection: str = Field(..., description="소속 컬렉션")
    title: str = Field(..., description="문서 제목")
    content_snippet: str = Field(..., description="내용 요약")
    highlighted_content: Optional[str] = Field(None, description="하이라이트된 내용")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")
    enrichment_data: Optional[EnrichmentData] = Field(None, description="보강 데이터")
    match_reasons: List[str] = Field(default_factory=list, description="매칭 이유")
    created_at: Optional[datetime] = Field(None, description="생성 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SearchResponse(BaseModel):
    """검색 응답 데이터"""
    query: str = Field(..., description="원본 검색 질의")
    results: List[SearchResult] = Field(default_factory=list, description="검색 결과 목록")
    total_count: int = Field(..., ge=0, description="전체 결과 개수")
    returned_count: int = Field(..., ge=0, description="반환된 결과 개수")
    search_time_ms: int = Field(..., ge=0, description="검색 소요 시간(ms)")
    query_id: str = Field(..., description="검색 세션 ID")
    search_strategy: str = Field(..., description="사용된 검색 전략")
    collections_searched: List[str] = Field(default_factory=list, description="검색된 컬렉션 목록")
    filters_applied: Optional[SearchFilters] = Field(None, description="적용된 필터")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    @field_validator('returned_count')
    @classmethod
    def validate_returned_count(cls, v: int, info) -> int:
        """반환 개수가 전체 개수보다 크지 않은지 검증"""
        total = info.data.get('total_count', 0)
        if v > total:
            raise ValueError("반환된 결과 개수는 전체 개수보다 클 수 없습니다")
        return v


class HealthStatus(BaseModel):
    """헬스체크 상태"""
    service: str = Field(default="search", description="서비스 이름")
    status: str = Field(..., description="상태 (healthy/unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.now, description="체크 시간")
    version: str = Field(default="1.0.0", description="서비스 버전")
    dependencies: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="의존성 상태")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="성능 메트릭")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SearchLog(BaseModel):
    """검색 로그"""
    query_id: str = Field(..., description="검색 ID")
    user_id: Optional[str] = Field(None, description="사용자 ID")
    query_text: str = Field(..., description="검색어")
    search_mode: SearchMode = Field(..., description="검색 모드")
    filters: Optional[SearchFilters] = Field(None, description="적용된 필터")
    result_count: int = Field(..., ge=0, description="결과 개수")
    search_time_ms: int = Field(..., ge=0, description="검색 시간(ms)")
    timestamp: datetime = Field(default_factory=datetime.now, description="검색 시간")
    success: bool = Field(default=True, description="성공 여부")
    error_message: Optional[str] = Field(None, description="에러 메시지")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SearchStats(BaseModel):
    """검색 통계"""
    total_searches: int = Field(default=0, description="전체 검색 횟수")
    successful_searches: int = Field(default=0, description="성공한 검색 횟수")
    failed_searches: int = Field(default=0, description="실패한 검색 횟수")
    average_response_time_ms: float = Field(default=0.0, description="평균 응답 시간(ms)")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="캐시 히트율")
    popular_queries: List[Dict[str, Any]] = Field(default_factory=list, description="인기 검색어")
    search_modes_distribution: Dict[str, int] = Field(default_factory=dict, description="검색 모드별 분포")
    collections_usage: Dict[str, int] = Field(default_factory=dict, description="컬렉션별 사용량")
    period_start: datetime = Field(..., description="통계 시작 시간")
    period_end: datetime = Field(..., description="통계 종료 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
