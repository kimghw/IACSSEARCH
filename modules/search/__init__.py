"""Search 모듈 공개 인터페이스

이 모듈은 벡터 기반 검색 기능을 제공합니다.
사용자의 자연어 질의를 임베딩으로 변환하여 Qdrant에서 유사도 검색을 수행합니다.

주요 기능:
- 자연어 질의 처리 및 임베딩 생성
- 벡터 유사도 검색 (순수 벡터 검색 및 하이브리드 검색)
- 다중 컬렉션 검색 지원
- 검색 결과 메타데이터 보강
- 검색 이력 및 통계 관리

사용 예시:
    from modules.search import SearchOrchestrator, SearchQuery, SearchMode
    
    # 검색 오케스트레이터 생성
    orchestrator = SearchOrchestrator()
    
    # 검색 요청 생성
    query = SearchQuery(
        query_text="프로젝트 관련 이메일",
        search_mode=SearchMode.HYBRID,
        limit=10
    )
    
    # 검색 실행
    response = await orchestrator.search_orchestrator_process(query)
"""

# 버전 정보
__version__ = "1.0.0"

# 공개 API import
# SearchOrchestrator는 아직 구현되지 않았으므로 주석 처리
# from .orchestrator import SearchOrchestrator

# 데이터 모델 공개
from .schema import (
    CollectionStrategy,
    SearchFilters,
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
    HealthStatus,
)

# 공개 API 목록
__all__ = [
    # 열거형
    "SearchMode",
    "CollectionStrategy",
    # 데이터 모델
    "SearchQuery",
    "SearchResponse",
    "SearchResult",
    "SearchFilters",
    "HealthStatus",
    # 오케스트레이터 (구현 후 추가)
    # "SearchOrchestrator",
    # 버전
    "__version__",
]

# 모듈 설명
__doc__ = """
Search 모듈 - 벡터 기반 검색 서비스

이 모듈은 사용자의 자연어 질의를 처리하여 벡터 유사도 기반의 검색을 수행합니다.

주요 구성요소:
- SearchOrchestrator: 검색 프로세스 전체를 조율하는 메인 클래스
- SearchQuery: 검색 요청 데이터 모델
- SearchResponse: 검색 응답 데이터 모델
- SearchMode: 검색 모드 (HYBRID, VECTOR_ONLY, FILTER_ONLY)
- CollectionStrategy: 컬렉션 선택 전략 (SINGLE, MULTIPLE, AUTO)

지원 기능:
1. 순수 벡터 검색: 필터 없이 의미적 유사도만으로 검색
2. 하이브리드 검색: 필터와 벡터 검색을 함께 사용
3. 다중 컬렉션 검색: 여러 컬렉션을 동시에 검색
4. 검색 결과 보강: 메타데이터 추가 및 스니펫 생성
5. 검색 이력 관리: 검색 로그 저장 및 통계 수집
"""
