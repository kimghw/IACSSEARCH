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
├── search_performance_monitor.py      # 성능 모니터링 (단일 기능)
├── cache_manager.py                   # 캐시 관리 (단일 기능)
├── repository.py                       # DB/API 접근 계층
└── schema.py                          # Pydantic 데이터 모델
```

## 상세 호출 흐름

### 1. 메인 검색 프로세스 (search_orchestrator_process)

```
API Gateway → SearchOrchestrator.search_orchestrator_process()
├── 1. 초기화 확인 (_ensure_initialized)
│   ├── _init_shared_dependencies() - 공통 의존성 초기화
│   │   ├── SearchRepository 싱글톤 생성
│   │   └── SearchCacheManager 싱글톤 생성
│   └── _inject_dependencies() - 각 서비스에 의존성 주입
├── 2. 요청 검증 (_search_orchestrator_validate_request)
│   ├── 빈 문자열 체크
│   ├── 길이 제한 체크 (최대 1000자)
│   └── 최소 길이 체크 (최소 2자)
├── 3. 질의 처리 (SearchQueryProcessor.search_query_process) - 조건부 실행
│   │   ※ VECTOR_ONLY 모드가 아니거나 auto_extract_filters=True일 때만 실행
│   ├── 캐시 확인 (cache_processed_query_get)
│   ├── 질의 검증 (search_query_validate)
│   ├── 질의 정규화 (search_query_normalize)
│   ├── 필터 추출 (search_query_extract_filters)
│   │   ├── 날짜 필터 파싱 (_search_query_parse_date_filters)
│   │   ├── 발신자 추출 (_extract_sender)
│   │   └── 수신자 추출 (_extract_recipients)
│   ├── 언어 감지 (_search_query_detect_language)
│   ├── 키워드 추출 (_search_query_extract_keywords)
│   └── 캐시 저장 (cache_processed_query_set)
├── 4. 임베딩 생성 (SearchEmbeddingService.search_embedding_create)
│   │   ※ 정규화된 텍스트(processed_query.normalized_text) 또는 원본 질의 사용
│   ├── 텍스트 정규화 (_search_embedding_normalize_text)
│   ├── 캐시 확인 (cache_embedding_get)
│   ├── OpenAI API 호출 (_create_embedding_with_retry)
│   │   ├── 재시도 로직 (최대 3회)
│   │   ├── 지수 백오프 적용
│   │   └── 에러 타입별 처리 (RateLimit, Timeout, APIError)
│   ├── 임베딩 검증 (search_embedding_validate)
│   └── 캐시 저장 (cache_embedding_set)
├── 5. 벡터 검색 (SearchVectorService.search_vector_find)
│   ├── 검색 모드별 분기
│   │   ├── VECTOR_ONLY: search_vector_find_pure()
│   │   ├── FILTER_ONLY: 필터만 사용 (미지원)
│   │   └── HYBRID: search_vector_find_with_filters()
│   ├── 컬렉션 선택 (search_vector_select_collections)
│   ├── 다중 컬렉션 검색 (search_vector_search_multiple_collections)
│   │   ├── 병렬 검색 실행 (asyncio.gather)
│   │   ├── 결과 병합 (search_vector_merge_collection_results)
│   │   ├── 점수 정규화 (_search_vector_normalize_scores_across_collections)
│   │   └── 중복 제거 (_search_vector_deduplicate)
│   └── 점수 임계값 적용 (search_vector_apply_score_threshold)
├── 6. 결과 보강 (SearchResultEnricher.search_result_enrich)
│   ├── 메타데이터 조회 (search_result_get_metadata)
│   │   ├── 캐시 확인 (cache_document_metadata_get)
│   │   ├── MongoDB 조회 (SearchRepository.search_repo_get_metadata)
│   │   └── 캐시 저장 (cache_document_metadata_set)
│   ├── 개별 결과 포맷팅 (search_result_format_single)
│   │   ├── 스니펫 생성 (search_result_generate_snippet)
│   │   │   ├── 콘텐츠 정리 (_clean_content_for_snippet)
│   │   │   ├── 검색어 위치 찾기 (_find_query_matches)
│   │   │   ├── 최적 스니펫 추출 (_extract_best_snippet)
│   │   │   └── 하이라이팅 적용 (_search_result_extract_highlight)
│   │   ├── 관련성 점수 계산 (_search_result_calculate_relevance)
│   │   └── 보강 데이터 생성 (EnrichmentData)
│   └── 결과 목록 반환
├── 7. 검색 로그 기록 (_search_orchestrator_log_search)
│   └── SearchRepository.search_repo_log_query()
│       ├── MongoDB 로그 저장
│       └── 캐시에 최근 검색 저장
└── 8. 응답 생성 및 통계 업데이트
    ├── 소요 시간 측정 (_search_orchestrator_measure_time)
    ├── 통계 업데이트 (_update_statistics)
    └── SearchResponse 반환
```

### 2. 의존성 주입 흐름 (_inject_dependencies)

```
SearchOrchestrator 초기화
├── 공통 의존성 초기화 (_init_shared_dependencies)
│   ├── SearchRepository 싱글톤 생성
│   │   └── _ensure_initialized() → MongoDB/Cache 연결
│   └── SearchCacheManager 싱글톤 생성
│       └── _ensure_initialized() → Redis 연결
├── 각 서비스 생성 (의존성 없이)
│   ├── SearchQueryProcessor()
│   ├── SearchEmbeddingService()
│   ├── SearchVectorService()
│   ├── SearchResultEnricher()
│   └── SearchPerformanceMonitor()
└── 의존성 주입 (set_dependencies)
    ├── QueryProcessor.set_dependencies(cache_manager=cache)
    ├── EmbeddingService.set_dependencies(cache_manager=cache)
    ├── VectorService.set_dependencies() - 의존성 없음
    ├── ResultEnricher.set_dependencies(repository=repo)
    └── PerformanceMonitor.set_dependencies(cache_manager=cache)
```

### 3. 캐싱 전략 흐름

```
캐시 확인 → 캐시 히트 → 즉시 반환
    ↓ (캐시 미스)
실제 처리 → 결과 생성 → 캐시 저장 → 반환

주요 캐시 키:
├── search:embedding:{text_hash} (TTL: 1시간)
├── search:processed_query:{query_hash} (TTL: 1시간)
├── search:vector:results:{query_hash}:{collection} (TTL: 10분)
├── search:metadata:{doc_id} (TTL: 30분)
└── search:recent:{user_id}:{query_id} (TTL: 5분)
```

### 4. 에러 처리 및 재시도 흐름

```
각 단계별 에러 처리:
├── 질의 검증 실패 → ValueError 발생
├── 임베딩 생성 실패 → 재시도 로직 (최대 3회)
│   ├── RateLimitError → 5초 대기 후 재시도
│   ├── Timeout → 지수 백오프 재시도
│   └── APIError → 즉시 실패
├── 벡터 검색 실패 → 빈 결과 반환
├── 메타데이터 조회 실패 → 기본 메타데이터로 대체
└── 로그 기록 실패 → 경고 로그만 출력 (검색 계속 진행)
```

### 5. 성능 최적화 포인트

```
병목 지점 및 최적화:
├── 임베딩 생성 (500ms 목표)
│   ├── 캐시 히트율 80% 이상 유지
│   └── 배치 처리 고려
├── 벡터 검색 (300ms 목표)
│   ├── 다중 컬렉션 병렬 처리
│   └── 점수 임계값으로 조기 종료
├── 메타데이터 조회 (200ms 목표)
│   ├── 배치 조회로 DB 호출 최소화
│   └── 캐시 적극 활용
└── 전체 응답 시간 (1초 이하 목표)
    ├── 비동기 처리 최대 활용
    └── 단계별 타임아웃 설정
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
- infra/vector_store.py (VectorStoreManager)
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

### 성능 모니터링 엔드포인트
```
GET /api/v1/search/metrics
Response: PerformanceMetrics

GET /api/v1/search/optimization
Response: OptimizationSuggestions
```

## 헬스체크 및 모니터링

### 헬스체크 프로세스 (search_orchestrator_health_check)

```
헬스체크 실행 흐름:
├── 1. Database 연결 상태 확인
│   └── get_database_manager() 호출 및 연결 테스트
├── 2. Cache 서비스 상태 확인
│   └── get_cache_service() 호출 및 테스트 키 조회
├── 3. Vector Store 연결 상태 확인
│   └── get_vector_manager() 호출 및 연결 테스트
├── 4. OpenAI API 상태 확인
│   └── 임베딩 서비스 통계를 통한 API 가용성 확인
└── 5. 전체 상태 평가 및 HealthStatus 반환
    ├── status: "healthy" | "degraded"
    ├── checks: 각 서비스별 상태
    └── stats: 전체 통계 정보
```

### 성능 모니터링 및 최적화

#### 성능 메트릭스 조회 (search_orchestrator_get_performance_metrics)
- **캐시 히트율**: 각 캐시 유형별 히트율 통계
- **응답 시간 분포**: P50, P95, P99 응답 시간
- **처리량**: 초당 요청 수 (RPS)
- **에러율**: 실패한 요청의 비율
- **리소스 사용량**: 메모리, CPU 사용률

#### 최적화 제안 (search_orchestrator_get_optimization_suggestions)
```
최적화 제안 생성 흐름:
├── 1. 캐시 전략 분석 (search_monitor_optimize_cache_strategy)
│   ├── 캐시 히트율 분석
│   ├── TTL 최적화 제안
│   └── 캐시 키 전략 개선안
├── 2. 병목 지점 식별 (search_monitor_identify_bottlenecks)
│   ├── 단계별 응답 시간 분석
│   ├── 리소스 사용량 패턴 분석
│   └── 성능 저하 원인 식별
└── 3. 종합 권장사항 생성 (_generate_recommendations_summary)
    ├── 우선순위별 개선 항목
    ├── 예상 성능 향상 효과
    └── 구현 복잡도 평가
```

#### 성능 최적화 권장사항 예시
- **캐시 히트율 < 80%**: TTL 조정 또는 캐시 키 전략 개선
- **평균 응답 시간 > 1초**: 병렬 처리 확대 또는 인덱스 최적화
- **임베딩 생성 시간 > 500ms**: 배치 처리 도입 또는 모델 변경 검토
- **메타데이터 조회 시간 > 200ms**: 배치 조회 또는 캐시 전략 강화

## 테스트 시나리오

1. **기본 검색 테스트**: 단순 자연어 질의
2. **필터 검색 테스트**: 날짜, 발신자 필터 적용
3. **성능 테스트**: 응답 시간 및 처리량 측정
4. **에러 처리 테스트**: 각종 실패 상황 처리
5. **헬스체크 테스트**: 각 의존성 서비스 상태 확인
6. **모니터링 테스트**: 성능 메트릭스 및 최적화 제안 검증

## 참조

- **UC-1**: usecases.md의 "Qdrant 벡터 검색 서비스"
- **프로젝트 아키텍쳐**: .clinerules/proejctArchitecture.md
- **인프라 설정**: infra/vector_store.py, infra/database.py
- **벡터 저장소**: VectorStoreManager 클래스 활용
