# Search 모듈 구현 작업 계획서

## 전체 작업 개요

### 목표
UC-1 벡터 검색 기능을 프로젝트 아키텍쳐 규칙을 준수하여 구현 (하이브리드 컬렉션 방식)

### 소요 기간
총 6일 (Phase별 1일씩)

### 핵심 원칙
- 오케스트레이터 패턴으로 호출 순서 제어
- 파일당 350줄 이하 유지
- 단일 기능 파일로 분할
- 모든 함수에 search_ 프리픽스 적용
- 과도한 추상화 금지
- **하이브리드 컬렉션 방식**: 기본 단일 컬렉션 + 선택적 다중 컬렉션
- **🆕 순수 벡터 검색**: 필터 없이 벡터 검색만 수행하는 모드
- **🆕 유연한 컬렉션 선택**: 단일/다중 컬렉션 검색 선택 기능

## Phase 1: 데이터 계약 정의 (1일)

### 1.1 schema.py 구현
**목표**: 모듈 간 데이터 계약 명확히 정의
**파일**: modules/search/schema.py

#### 구현할 클래스:
```python
# 🆕 새로운 검색 모드 관련 모델
- SearchMode: 검색 모드 열거형 (HYBRID, VECTOR_ONLY, FILTER_ONLY)
- CollectionStrategy: 컬렉션 선택 전략 (SINGLE, MULTIPLE, AUTO)

# 입력 관련 모델
- SearchQuery: 검색 요청 데이터 (🆕 search_mode, collection_strategy 추가)
- SearchFilters: 검색 필터 옵션
- ProcessedQuery: 전처리된 질의

# 중간 처리 모델
- EmbeddingRequest: 임베딩 요청 데이터
- VectorMatch: 벡터 검색 결과 (🆕 collection_name 추가)
- EnrichmentData: 메타데이터 보강 정보

# 출력 관련 모델
- SearchResult: 개별 검색 결과 (🆕 source_collection 추가)
- SearchResponse: 최종 응답 데이터 (🆕 search_strategy, collections_searched 추가)
- HealthStatus: 헬스체크 상태
```

#### 검증 규칙:
- query_text: 1-1000자 제한
- limit: 1-100 범위 제한
- score_threshold: 0.0-1.0 범위
- 필수 필드 검증

### 1.2 __init__.py 구현
**목표**: 모듈 공개 인터페이스 정의
**파일**: modules/search/__init__.py

#### 공개할 클래스/함수:
```python
from .orchestrator import SearchOrchestrator
from .schema import SearchQuery, SearchResponse, SearchFilters
```

**완료 기준**:
- [ ] 모든 데이터 모델 정의 완료
- [ ] Pydantic 검증 규칙 적용
- [ ] 공개 인터페이스 정의
- [ ] 타입 힌트 100% 적용

## Phase 2: 인프라 계층 구현 (1일)

### 2.1 repository.py 구현  
**목표**: DB/API 접근 계층 구현
**파일**: modules/search/repository.py

#### 구현할 클래스:
```python
class SearchRepository:
    def __init__(self, db_manager: DatabaseManager, cache: CacheService)
    
    # 검색 로그 관리
    async def search_repo_log_query(self, query: str, results: List[SearchResult]) -> str
    async def search_repo_get_search_history(self, user_id: str) -> List[SearchLog]
    
    # 메타데이터 조회
    async def search_repo_get_metadata(self, document_ids: List[str]) -> Dict[str, Any]
    async def search_repo_get_email_details(self, email_id: str) -> Optional[EmailData]
    
    # 캐시 관리
    async def search_repo_cache_get(self, key: str) -> Optional[Any]
    async def search_repo_cache_set(self, key: str, value: Any, ttl: int) -> None
    
    # 통계 관리
    async def search_repo_update_stats(self, query_type: str, response_time: float) -> None
```

#### MongoDB 컬렉션:
- search_logs: 검색 이력 저장
- search_stats: 검색 통계 저장
- emails: 이메일 메타데이터 (기존 활용)

**완료 기준**:
- [ ] 모든 DB 접근 함수 구현
- [ ] Redis 캐시 연동 구현
- [ ] 에러 처리 로직 구현
- [ ] 비동기 처리 적용

## Phase 3: 단일 기능 서비스 구현 (2일)

### 3.1 search_query_processor.py (0.5일)
**목표**: 질의 처리 전용 서비스
**파일**: modules/search/search_query_processor.py

#### 구현할 클래스:
```python
class SearchQueryProcessor:
    def __init__(self, cache: CacheService)
    
    # 메인 처리 함수
    async def search_query_process(self, query_text: str, filters: Optional[SearchFilters]) -> ProcessedQuery
    
    # 개별 처리 함수
    async def search_query_validate(self, query_text: str) -> ValidationResult
    async def search_query_normalize(self, query_text: str) -> str
    async def search_query_extract_filters(self, query_text: str) -> SearchFilters
    
    # 내부 함수
    async def _search_query_clean_text(self, text: str) -> str
    async def _search_query_detect_language(self, text: str) -> str
    async def _search_query_parse_date_filters(self, text: str) -> Optional[DateRange]
```

#### 처리 로직:
1. 입력 검증 (길이, 문자 제한)
2. 텍스트 정규화 (특수문자 제거, 소문자 변환)
3. 자연어에서 필터 추출
4. 캐시 확인 및 저장

### 3.2 search_embedding_service.py (0.5일)
**목표**: 임베딩 생성 전용 서비스
**파일**: modules/search/search_embedding_service.py

#### 구현할 클래스:
```python
class SearchEmbeddingService:
    def __init__(self, vector_manager: VectorStoreManager, cache: CacheService)
    
    # 메인 처리 함수
    async def search_embedding_create(self, text: str) -> List[float]
    
    # 캐시 관리
    async def search_embedding_cache_get(self, text: str) -> Optional[List[float]]
    async def search_embedding_cache_set(self, text: str, embedding: List[float]) -> None
    
    # 검증 및 최적화
    async def search_embedding_validate(self, embedding: List[float]) -> bool
    async def _search_embedding_normalize_text(self, text: str) -> str
    async def _search_embedding_generate_cache_key(self, text: str) -> str
```

#### 처리 로직:
1. 캐시에서 임베딩 조회
2. 없으면 OpenAI API 호출
3. 임베딩 검증 및 정규화
4. 캐시에 저장 (TTL 1시간)

### 3.3 search_vector_service.py (0.5일)
**목표**: 벡터 검색 전용 서비스 (🆕 순수 벡터 검색 + 다중 컬렉션 지원)
**파일**: modules/search/search_vector_service.py

#### 구현할 클래스:
```python
class SearchVectorService:
    def __init__(self, vector_manager: VectorStoreManager)
    
    # 🆕 메인 검색 함수 (검색 모드별 분기)
    async def search_vector_find(self, embedding: List[float], query: SearchQuery) -> List[VectorMatch]
    
    # 🆕 순수 벡터 검색 (필터 없음)
    async def search_vector_find_pure(self, embedding: List[float], collections: List[str], limit: int, score_threshold: float) -> List[VectorMatch]
    
    # 기존 하이브리드 검색 (필터 + 벡터)
    async def search_vector_find_with_filters(self, embedding: List[float], filters: SearchFilters, collections: List[str], limit: int) -> List[VectorMatch]
    
    # 🆕 컬렉션 선택 로직
    async def search_vector_select_collections(self, strategy: CollectionStrategy, target_collections: Optional[List[str]]) -> List[str]
    async def search_vector_get_available_collections(self) -> List[str]
    
    # 🆕 다중 컬렉션 검색
    async def search_vector_search_multiple_collections(self, embedding: List[float], collections: List[str], filters: Optional[SearchFilters], limit: int) -> List[VectorMatch]
    async def search_vector_merge_collection_results(self, collection_results: Dict[str, List[VectorMatch]], limit: int) -> List[VectorMatch]
    
    # 필터 처리
    async def search_vector_build_filter(self, filters: SearchFilters) -> QdrantFilter
    async def search_vector_apply_score_threshold(self, matches: List[VectorMatch], threshold: float) -> List[VectorMatch]
    
    # 결과 최적화
    async def _search_vector_deduplicate(self, matches: List[VectorMatch]) -> List[VectorMatch]
    async def _search_vector_sort_by_relevance(self, matches: List[VectorMatch]) -> List[VectorMatch]
    async def _search_vector_normalize_scores_across_collections(self, matches: List[VectorMatch]) -> List[VectorMatch]
```

#### 🆕 새로운 처리 로직:
1. **검색 모드별 분기 처리**:
   - VECTOR_ONLY: search_vector_find_pure() 호출
   - HYBRID: search_vector_find_with_filters() 호출
   - FILTER_ONLY: 벡터 검색 생략

2. **컬렉션 선택 전략**:
   - SINGLE: 기본 컬렉션 하나만 선택
   - MULTIPLE: 지정된 여러 컬렉션에서 검색
   - AUTO: 질의 내용에 따라 자동 선택

3. **다중 컬렉션 검색 및 결과 병합**:
   - 각 컬렉션별 병렬 검색 실행
   - 점수 정규화 후 통합 정렬
   - 중복 제거 및 최종 결과 반환

4. **순수 벡터 검색 최적화**:
   - 필터 처리 생략으로 성능 향상
   - 의미적 유사도만으로 순수 검색
   - 탐색적 검색에 최적화

### 3.4 search_result_enricher.py (0.5일)
**목표**: 검색 결과 보강 전용 서비스
**파일**: modules/search/search_result_enricher.py

#### 구현할 클래스:
```python
class SearchResultEnricher:
    def __init__(self, repository: SearchRepository)
    
    # 메인 보강 함수
    async def search_result_enrich(self, vector_matches: List[VectorMatch]) -> List[SearchResult]
    
    # 메타데이터 처리
    async def search_result_get_metadata(self, document_ids: List[str]) -> Dict[str, Any]
    async def search_result_generate_snippet(self, content: str, query: str) -> str
    
    # 결과 포맷팅
    async def search_result_format_single(self, match: VectorMatch, metadata: Dict) -> SearchResult
    async def _search_result_calculate_relevance(self, match: VectorMatch, metadata: Dict) -> float
    async def _search_result_extract_highlight(self, text: str, query: str) -> str
```

#### 처리 로직:
1. document_id로 MongoDB에서 메타데이터 조회
2. 검색어 기반 스니펫 생성
3. 관련성 점수 계산
4. 최종 SearchResult 포맷팅

**완료 기준**:
- [ ] 4개 서비스 모두 구현 완료
- [ ] 각 파일 350줄 이하 유지
- [ ] 비동기 처리 100% 적용
- [ ] 에러 처리 로직 포함

## Phase 4: 오케스트레이션 구현 (1일)

### 4.1 orchestrator.py 구현
**목표**: 전체 검색 프로세스 조율
**파일**: modules/search/orchestrator.py

#### 구현할 클래스:
```python
class SearchOrchestrator:
    def __init__(self):
        self.query_processor = SearchQueryProcessor(get_cache_service())
        self.embedding_service = SearchEmbeddingService(get_vector_manager(), get_cache_service())
        self.vector_service = SearchVectorService(get_vector_manager())
        self.result_enricher = SearchResultEnricher(SearchRepository())
        self.repository = SearchRepository()
    
    # 메인 오케스트레이션 함수
    async def search_orchestrator_process(self, query_text: str, filters: Optional[SearchFilters] = None, limit: int = 20, score_threshold: float = 0.7) -> SearchResponse
    
    # 헬스체크
    async def search_orchestrator_health_check() -> HealthStatus
    
    # 내부 조율 함수
    async def _search_orchestrator_validate_request(self, query_text: str) -> None
    async def _search_orchestrator_measure_time(self, start_time: float) -> int
    async def _search_orchestrator_log_search(self, query: str, results: List[SearchResult], search_time: int) -> str
```

#### 오케스트레이션 플로우:
```python
async def search_orchestrator_process(self, query_text: str, **kwargs) -> SearchResponse:
    start_time = time.time()
    
    # 1. 요청 검증
    await self._search_orchestrator_validate_request(query_text)
    
    # 2. 질의 처리
    processed_query = await self.query_processor.search_query_process(query_text, filters)
    
    # 3. 임베딩 생성
    embedding = await self.embedding_service.search_embedding_create(processed_query.text)
    
    # 4. 벡터 검색
    vector_matches = await self.vector_service.search_vector_find(embedding, processed_query.filters, limit)
    
    # 5. 결과 보강
    enriched_results = await self.result_enricher.search_result_enrich(vector_matches)
    
    # 6. 응답 생성
    search_time = self._search_orchestrator_measure_time(start_time)
    query_id = await self._search_orchestrator_log_search(query_text, enriched_results, search_time)
    
    return SearchResponse(
        query=query_text,
        results=enriched_results,
        total_count=len(enriched_results),
        search_time_ms=search_time,
        query_id=query_id
    )
```

**완료 기준**:
- [ ] 오케스트레이션 플로우 구현
- [ ] 모든 서비스 연동 완료
- [ ] 에러 처리 및 로깅 구현
- [ ] 성능 측정 로직 구현

## Phase 5: API 통합 (1일)

### 5.1 FastAPI 엔드포인트 구현
**위치**: main/api_gateway.py에 추가
**목표**: REST API 인터페이스 제공

#### 구현할 엔드포인트:
```python
@app.post("/api/v1/search", response_model=SearchResponse)
async def search_endpoint(request: SearchQuery) -> SearchResponse:
    orchestrator = SearchOrchestrator()
    return await orchestrator.search_orchestrator_process(
        query_text=request.query_text,
        filters=request.filters,
        limit=request.limit,
        score_threshold=request.score_threshold
    )

@app.get("/api/v1/search/health")
async def search_health_check():
    orchestrator = SearchOrchestrator()
    return await orchestrator.search_orchestrator_health_check()
```

### 5.2 에러 처리 미들웨어
```python
@app.exception_handler(SearchValidationError)
async def search_validation_exception_handler(request: Request, exc: SearchValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid search query", "detail": str(exc)}
    )
```

**완료 기준**:
- [ ] API 엔드포인트 구현
- [ ] 에러 처리 미들웨어 구현
- [ ] API 문서 자동 생성
- [ ] 기본 인증 구현

## Phase 6: 테스트 및 검증 (1일)

### 6.1 시나리오 테스트 작성
**위치**: tests/scenario/search_service_scenario.py

#### 테스트 시나리오:
1. **기본 검색 테스트**
   - 단순 자연어 질의
   - 결과 개수 확인
   - 응답 시간 측정

2. **필터 검색 테스트**
   - 날짜 범위 필터
   - 발신자 필터
   - 복합 필터 조건

3. **성능 테스트**
   - 동시 요청 처리
   - 대용량 결과 처리
   - 캐시 성능 확인

4. **에러 처리 테스트**
   - 잘못된 입력 처리
   - 서비스 장애 시나리오
   - 타임아웃 처리

### 6.2 성능 최적화
1. **캐시 최적화**
   - 임베딩 캐시 히트율 확인
   - 결과 캐시 전략 조정

2. **쿼리 최적화**
   - MongoDB 인덱스 확인
   - Qdrant 검색 파라미터 튜닝

3. **메모리 최적화**
   - 대용량 결과 스트리밍
   - 불필요한 객체 정리

**완료 기준**:
- [ ] 모든 시나리오 테스트 통과
- [ ] 성능 목표 달성 (응답시간 1초 이하)
- [ ] 캐시 히트율 80% 이상
- [ ] 메모리 사용량 최적화

## 전체 검증 체크리스트

### 프로젝트 아키텍쳐 규칙 준수
- [ ] 오케스트레이터에서만 호출 순서 정의
- [ ] 모든 함수에 search_ 프리픽스 적용
- [ ] 파일당 350줄 이하 유지
- [ ] 단일 기능별 파일 분할
- [ ] 모듈간 단방향 의존성 유지

### 기능 요구사항
- [ ] UC-1 벡터 검색 기능 완전 구현
- [ ] 자연어 질의 처리
- [ ] 임베딩 기반 검색
- [ ] 메타데이터 보강
- [ ] 검색 로그 기록

### 비기능 요구사항
- [ ] 응답 시간 1초 이하
- [ ] 동시 요청 50개 이상 처리
- [ ] 캐시 히트율 80% 이상
- [ ] 에러 처리 100% 적용

### 코드 품질
- [ ] 타입 힌트 100% 적용
- [ ] 비동기 처리 100% 적용
- [ ] 로깅 모든 단계 적용
- [ ] 문서화 완료

## 리스크 및 대응방안

### 기술적 리스크
1. **OpenAI API 지연**
   - 대응: 임베딩 캐시 강화
   - 대응: 타임아웃 설정 및 재시도 로직

2. **Qdrant 성능 이슈**
   - 대응: 인덱스 최적화
   - 대응: 결과 캐싱 강화

3. **메모리 부족**
   - 대응: 스트리밍 처리
   - 대응: 결과 크기 제한

### 일정 리스크
1. **구현 복잡도 증가**
   - 대응: 단순화 우선 원칙 적용
   - 대응: MVP 기능 먼저 구현

2. **통합 테스트 지연**
   - 대응: 각 Phase별 검증 강화
   - 대응: 모킹을 활용한 단위 테스트

## 🆕 새로운 기능 구현 작업 순서

### 작업 A: 순수 벡터 검색 기능 구현

#### A.1 SearchQuery 스키마 확장 (30분)
**위치**: modules/search/schema.py
```python
class SearchMode(str, Enum):
    """검색 모드"""
    HYBRID = "hybrid"          # 필터 + 벡터 검색 (기본)
    VECTOR_ONLY = "vector_only"  # 순수 벡터 검색
    FILTER_ONLY = "filter_only"  # 필터만 검색

class SearchQuery(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=1000)
    search_mode: SearchMode = Field(default=SearchMode.HYBRID)
    use_filters: bool = Field(default=True)
    auto_extract_filters: bool = Field(default=True)
    # 기존 필드들...
```

#### A.2 SearchVectorService 순수 검색 메서드 추가 (1시간)
**위치**: modules/search/search_vector_service.py
```python
async def search_vector_find_pure(self, embedding: List[float], collections: List[str], limit: int, score_threshold: float) -> List[VectorMatch]:
    """순수 벡터 검색 (필터 없음)"""
    # 구현 내용...

async def search_vector_find(self, embedding: List[float], query: SearchQuery) -> List[VectorMatch]:
    """검색 모드에 따른 분기 처리"""
    if query.search_mode == SearchMode.VECTOR_ONLY:
        return await self.search_vector_find_pure(embedding, query.collections, query.limit, query.score_threshold)
    # 기존 로직...
```

#### A.3 Orchestrator 로직 수정 (30분)
**위치**: modules/search/orchestrator.py
```python
async def search_orchestrator_process(self, query: SearchQuery) -> SearchResponse:
    # 검색 모드별 분기 처리 추가
    if query.search_mode == SearchMode.VECTOR_ONLY:
        # 필터 추출 생략
        embedding = await self.embedding_service.search_embedding_create(query.query_text)
        vector_matches = await self.vector_service.search_vector_find_pure(embedding, query.collections, query.limit, query.score_threshold)
    # 기존 로직...
```

### 작업 B: 다중 컬렉션 선택 기능 구현

#### B.1 CollectionStrategy 열거형 정의 (20분)
**위치**: modules/search/schema.py
```python
class CollectionStrategy(str, Enum):
    """컬렉션 선택 전략"""
    SINGLE = "single"      # 기본 컬렉션 하나만
    MULTIPLE = "multiple"  # 지정된 여러 컬렉션
    AUTO = "auto"         # 자동 선택

class SearchQuery(BaseModel):
    # 기존 필드들...
    collection_strategy: CollectionStrategy = Field(default=CollectionStrategy.SINGLE)
    target_collections: Optional[List[str]] = Field(default=None)
```

#### B.2 컬렉션 선택 로직 구현 (1.5시간)
**위치**: modules/search/search_vector_service.py
```python
async def search_vector_select_collections(self, strategy: CollectionStrategy, target_collections: Optional[List[str]]) -> List[str]:
    """컬렉션 선택 전략에 따른 컬렉션 목록 반환"""
    if strategy == CollectionStrategy.SINGLE:
        return ["emails"]  # 기본 컬렉션
    elif strategy == CollectionStrategy.MULTIPLE:
        return target_collections or ["emails"]
    elif strategy == CollectionStrategy.AUTO:
        # 자동 선택 로직 (질의 분석 기반)
        return await self._auto_select_collections(query_text)

async def search_vector_search_multiple_collections(self, embedding: List[float], collections: List[str], filters: Optional[SearchFilters], limit: int) -> List[VectorMatch]:
    """다중 컬렉션 병렬 검색"""
    tasks = []
    for collection in collections:
        task = self._search_single_collection(embedding, collection, filters, limit)
        tasks.append(task)
    
    collection_results = await asyncio.gather(*tasks, return_exceptions=True)
    return await self.search_vector_merge_collection_results(dict(zip(collections, collection_results)), limit)

async def search_vector_merge_collection_results(self, collection_results: Dict[str, List[VectorMatch]], limit: int) -> List[VectorMatch]:
    """컬렉션별 결과 병합 및 정규화"""
    all_matches = []
    for collection_name, matches in collection_results.items():
        if isinstance(matches, list):  # 예외가 아닌 경우만
            # 컬렉션별 점수 정규화
            normalized_matches = await self._search_vector_normalize_scores_across_collections(matches)
            all_matches.extend(normalized_matches)
    
    # 통합 정렬 및 제한
    sorted_matches = sorted(all_matches, key=lambda x: x.score, reverse=True)
    return sorted_matches[:limit]
```

#### B.3 API 인터페이스 확장 (30분)
**위치**: main/api_gateway.py
```python
@app.post("/api/v1/search", response_model=SearchResponse)
async def search_endpoint(request: SearchQuery) -> SearchResponse:
    orchestrator = SearchOrchestrator()
    return await orchestrator.search_orchestrator_process(request)

# 🆕 순수 벡터 검색 전용 엔드포인트
@app.post("/api/v1/search/vector", response_model=SearchResponse)
async def vector_only_search(request: VectorOnlySearchQuery) -> SearchResponse:
    request.search_mode = SearchMode.VECTOR_ONLY
    orchestrator = SearchOrchestrator()
    return await orchestrator.search_orchestrator_process(request)

# 🆕 컬렉션 목록 조회 엔드포인트
@app.get("/api/v1/search/collections")
async def get_available_collections() -> List[str]:
    vector_service = SearchVectorService(get_vector_manager())
    return await vector_service.search_vector_get_available_collections()
```

### 작업 C: 테스트 시나리오 추가

#### C.1 순수 벡터 검색 테스트 (30분)
**위치**: tests/scenario/search_vector_only_scenario.py
```python
async def test_vector_only_search():
    """순수 벡터 검색 테스트"""
    query = SearchQuery(
        query_text="프로젝트 관련 문서",
        search_mode=SearchMode.VECTOR_ONLY,
        limit=10
    )
    
    response = await search_orchestrator.search_orchestrator_process(query)
    
    assert response.search_strategy == "vector_only"
    assert len(response.results) <= 10
    assert response.search_time_ms < 1000

async def test_vector_vs_hybrid_comparison():
    """순수 벡터 검색 vs 하이브리드 검색 비교"""
    query_text = "KR의 의견"
    
    # 순수 벡터 검색
    vector_query = SearchQuery(query_text=query_text, search_mode=SearchMode.VECTOR_ONLY)
    vector_response = await search_orchestrator.search_orchestrator_process(vector_query)
    
    # 하이브리드 검색
    hybrid_query = SearchQuery(query_text=query_text, search_mode=SearchMode.HYBRID)
    hybrid_response = await search_orchestrator.search_orchestrator_process(hybrid_query)
    
    # 결과 비교 분석
    assert len(vector_response.results) >= len(hybrid_response.results)
    # 하이브리드가 더 정확한 결과를 반환해야 함
```

#### C.2 다중 컬렉션 검색 테스트 (30분)
**위치**: tests/scenario/search_multi_collection_scenario.py
```python
async def test_single_collection_search():
    """단일 컬렉션 검색 테스트"""
    query = SearchQuery(
        query_text="회의 관련",
        collection_strategy=CollectionStrategy.SINGLE,
        target_collections=["emails"]
    )
    
    response = await search_orchestrator.search_orchestrator_process(query)
    
    assert all(result.source_collection == "emails" for result in response.results)

async def test_multiple_collection_search():
    """다중 컬렉션 검색 테스트"""
    query = SearchQuery(
        query_text="프로젝트 업데이트",
        collection_strategy=CollectionStrategy.MULTIPLE,
        target_collections=["emails", "documents", "messages"]
    )
    
    response = await search_orchestrator.search_orchestrator_process(query)
    
    # 여러 컬렉션에서 결과가 나와야 함
    collections_in_results = set(result.source_collection for result in response.results)
    assert len(collections_in_results) >= 1
    assert "emails" in response.collections_searched

async def test_auto_collection_selection():
    """자동 컬렉션 선택 테스트"""
    query = SearchQuery(
        query_text="이메일 관련 문의",
        collection_strategy=CollectionStrategy.AUTO
    )
    
    response = await search_orchestrator.search_orchestrator_process(query)
    
    # "이메일"이라는 키워드로 인해 emails 컬렉션이 자동 선택되어야 함
    assert "emails" in response.collections_searched
```

### 작업 D: 문서화 업데이트

#### D.1 README.md 업데이트 (20분)
**위치**: modules/search/README.md
```markdown
## 🆕 새로운 기능

### 순수 벡터 검색
- 필터 없이 의미적 유사도만으로 검색
- 탐색적 검색에 최적화
- 더 빠른 응답 속도

### 유연한 컬렉션 선택
- 단일 컬렉션: 기본 이메일 컬렉션만 검색
- 다중 컬렉션: 여러 컬렉션 동시 검색
- 자동 선택: 질의 내용에 따른 최적 컬렉션 자동 선택
```

#### D.2 API 문서 업데이트 (15분)
**위치**: docs/api/search_api.md
```markdown
## 새로운 API 엔드포인트

### POST /api/v1/search/vector
순수 벡터 검색 전용 엔드포인트

### GET /api/v1/search/collections
사용 가능한 컬렉션 목록 조회
```

### 전체 작업 소요 시간 예상

| 작업 | 소요 시간 |
|------|-----------|
| A.1 스키마 확장 | 30분 |
| A.2 순수 벡터 검색 구현 | 1시간 |
| A.3 오케스트레이터 수정 | 30분 |
| B.1 컬렉션 전략 정의 | 20분 |
| B.2 다중 컬렉션 로직 구현 | 1.5시간 |
| B.3 API 인터페이스 확장 | 30분 |
| C.1 순수 벡터 테스트 | 30분 |
| C.2 다중 컬렉션 테스트 | 30분 |
| D.1 README 업데이트 | 20분 |
| D.2 API 문서 업데이트 | 15분 |
| **총 소요 시간** | **5시간 25분** |

### 구현 우선순위

1. **1순위 (핵심 기능)**: A.1, A.2, A.3 - 순수 벡터 검색
2. **2순위 (컬렉션 선택)**: B.1, B.2 - 다중 컬렉션 기능  
3. **3순위 (API 확장)**: B.3 - API 인터페이스
4. **4순위 (검증)**: C.1, C.2 - 테스트 시나리오
5. **5순위 (문서화)**: D.1, D.2 - 문서 업데이트

이 작업 계획에 따라 구현하면 요청하신 두 가지 새로운 기능을 프로젝트 아키텍쳐 규칙을 준수하면서 효율적으로 추가할 수 있습니다.
