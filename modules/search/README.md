# Search 모듈 작업 계획서

## 개요
UC-1 벡터 검색 기능을 구현하는 모듈로, 자연어 질의를 임베딩으로 변환하여 Qdrant에서 유사도 검색을 수행하고 메타데이터와 함께 결과를 반환합니다.

## 모듈 구조

### 파일 구성 (프로젝트 아키텍쳐 규칙 준수)
```
modules/search/
├── README.md                           # 모듈 작업 계획서
├── __init__.py                         # 모듈 공개 인터페이스
├── orchestrator.py                     # 검색 프로세스 오케스트레이터
├── search_query_processor.py          # 질의 처리 (단일 기능)
├── search_embedding_service.py        # 임베딩 생성 (단일 기능)
├── search_vector_service.py           # 벡터 검색 (단일 기능)
├── search_result_enricher.py          # 결과 보강 (단일 기능)
├── repository.py                       # DB/API 접근 계층
└── schema.py                          # Pydantic 데이터 모델
```

## 호출 스택 (오케스트레이터 패턴)

```
FastAPI Endpoint
    ↓
SearchOrchestrator.search_orchestrator_process()
    ├── SearchQueryProcessor.search_query_process()
    ├── SearchEmbeddingService.search_embedding_create()
    ├── SearchVectorService.search_vector_find()
    ├── SearchResultEnricher.search_result_enrich()
    └── SearchRepository.search_repo_log()
```

## 입출력 데이터

### 입력
- **query_text** (str): 자연어 검색 질의
- **filters** (Optional[SearchFilters]): 검색 필터 옵션
- **limit** (int): 결과 개수 제한 (기본값: 20)
- **score_threshold** (float): 유사도 점수 임계값 (기본값: 0.7)
- **collections** (Optional[List[str]]): 검색할 컬렉션 목록 (기본값: 전체 컬렉션)

### 출력
- **SearchResponse**: 검색 결과 응답
  - query: 원본 질의
  - results: List[SearchResult] 검색 결과 목록
  - total_count: 전체 결과 개수
  - search_time_ms: 검색 소요 시간
  - query_id: 검색 세션 ID

## 의존성 구조 (레이지 싱글톤 패턴)

### 의존성 관리 아키텍쳐
SearchOrchestrator가 레이지 싱글톤 패턴을 사용하여 공통 의존성을 관리하고, 각 서비스에 의존성을 주입하는 중앙 관리자 역할을 수행합니다.

```
SearchOrchestrator (중앙 관리자)
├── 공통 의존성 (클래스 레벨 싱글톤)
│   ├── SearchRepository (단일 인스턴스)
│   └── SearchCacheManager (단일 인스턴스)
└── 서비스별 의존성 주입
    ├── SearchQueryProcessor ← CacheManager
    ├── SearchEmbeddingService ← CacheManager
    ├── SearchVectorService ← (의존성 없음)
    ├── SearchResultEnricher ← Repository
    └── SearchPerformanceMonitor ← CacheManager
```

### 의존성 주입 플로우
1. **공통 의존성 초기화**: Repository와 CacheManager를 싱글톤으로 생성
2. **서비스 생성**: 각 서비스를 의존성 없이 생성
3. **의존성 주입**: Orchestrator가 각 서비스에 필요한 의존성만 주입
4. **서비스 활용**: 각 서비스는 주입받은 의존성을 사용하여 작업 수행

### 내부 의존성
- infra/core/vector_store.py (VectorStoreManager)
- infra/cache.py (CacheService) 
- infra/database.py (DatabaseManager)
- modules/search/cache_manager.py (SearchCacheManager)

### 외부 의존성
- OpenAI API (임베딩 생성)
- Qdrant (벡터 검색)
- MongoDB (메타데이터 저장)


## 구현 우선순위

### Phase 1: 데이터 계약 정의 (1일)
1. schema.py - 모든 데이터 모델 정의
2. __init__.py - 공개 인터페이스 정의

### Phase 2: 인프라 계층 (1일)
1. repository.py - DB/API 접근 계층 구현

### Phase 3: 단일 기능 서비스 (2일)
1. search_query_processor.py - 질의 처리
2. search_embedding_service.py - 임베딩 생성
3. search_vector_service.py - 벡터 검색
4. search_result_enricher.py - 결과 보강

### Phase 4: 오케스트레이션 (1일)
1. orchestrator.py - 전체 프로세스 조율

### Phase 5: 테스트 및 최적화 (1일)
1. 시나리오 테스트 작성
2. 성능 최적화
3. 문서화 완료

## 명명 규칙 (프로젝트 아키텍쳐 규칙 준수)

### 클래스명
- SearchOrchestrator
- SearchQueryProcessor
- SearchEmbeddingService
- SearchVectorService
- SearchResultEnricher
- SearchRepository

### 공개 함수명 (search_클래스명_기능)
- search_orchestrator_process()
- search_query_process()
- search_embedding_create()
- search_vector_find()
- search_result_enrich()
- search_repo_log()

### 내부 함수명 (_search_클래스명_기능)
- _search_query_normalize()
- _search_embedding_validate()
- _search_vector_filter()
- _search_result_format()

## 성능 목표

- **검색 응답 시간**: 1초 이하
- **임베딩 생성 시간**: 500ms 이하
- **캐시 적중률**: 80% 이상
- **동시 검색 요청**: 50개 이상

## 에러 처리 전략

1. **입력 검증 에러**: SearchQueryProcessor에서 처리
2. **임베딩 생성 실패**: 재시도 로직 (최대 3회)
3. **벡터 검색 실패**: 캐시된 결과 반환
4. **메타데이터 조회 실패**: 부분 결과 허용

## 로깅 전략

- **DEBUG**: 개발용 상세 로그
- **INFO**: 비즈니스 로직 실행 로그
- **WARN**: 성능 이슈 및 주의사항
- **ERROR**: 시스템 오류 및 예외

## 캐싱 전략

1. **질의 임베딩 캐시**: Redis, TTL 1시간
2. **검색 결과 캐시**: Redis, TTL 10분
3. **메타데이터 캐시**: Redis, TTL 30분

## API 인터페이스

### 검색 엔드포인트
```
POST /api/v1/search
Request Body: SearchQuery
Response: SearchResponse
```

### 헬스체크 엔드포인트
```
GET /api/v1/search/health
Response: HealthStatus
```

## 테스트 시나리오

1. **기본 검색 테스트**: 단순 자연어 질의
2. **필터 검색 테스트**: 날짜, 발신자 필터 적용
3. **성능 테스트**: 응답 시간 및 처리량 측정
4. **에러 처리 테스트**: 각종 실패 상황 처리

## 참조

- **UC-1**: usecases.md의 "Qdrant 벡터 검색 서비스"
- **프로젝트 아키텍쳐**: ../Documents/Cline/Rules/proejctArchitecture.md
- **인프라 설정**: infra/core/vector_store.py, infra/core/database.py
- **벡터 저장소**: VectorStoreManager 클래스 활용
