# Search 모듈 구현 작업 계획

## 🎯 목표
UC-1 벡터 검색 기능을 6일 일정으로 구현

## 📋 작업 전 체크리스트
- [x] WORK_PLAN.md 검토 완료
- [x] README.md 검토 완료
- [ ] infra/core/ 모듈 사용 가능 여부 확인
- [ ] 프로젝트 아키텍쳐 규칙 숙지

## 📅 일별 구현 계획

### Day 1: 데이터 계약 정의 (12월 13일)

#### 1-1. schema.py 구현 (오전)
```python
# 구현할 모델들:
- SearchMode (Enum)
- CollectionStrategy (Enum)
- SearchQuery (BaseModel)
- SearchFilters (BaseModel)
- ProcessedQuery (BaseModel)
- EmbeddingRequest (BaseModel)
- VectorMatch (BaseModel)
- EnrichmentData (BaseModel)
- SearchResult (BaseModel)
- SearchResponse (BaseModel)
- HealthStatus (BaseModel)
```

**작업 항목:**
- [ ] Pydantic v2 BaseModel 사용
- [ ] Field 검증 규칙 추가
- [ ] 타입 힌트 100% 적용
- [ ] 모델별 docstring 작성

#### 1-2. __init__.py 구현 (오후)
```python
# 공개 인터페이스:
from .orchestrator import SearchOrchestrator
from .schema import SearchQuery, SearchResponse, SearchFilters, SearchMode, CollectionStrategy
```

**검증 항목:**
- [ ] 순환 참조 없음 확인
- [ ] 공개 API만 노출

### Day 2: 인프라 계층 구현 (12월 14일)

#### 2-1. repository.py 구현
```python
class SearchRepository:
    # MongoDB 연동
    # Redis 캐시 연동
    # 로깅 및 통계 저장
```

**구현 순서:**
1. [ ] DatabaseManager 연동 설정
2. [ ] CacheService 연동 설정
3. [ ] search_repo_log_query() 구현
4. [ ] search_repo_get_metadata() 구현
5. [ ] search_repo_cache_get/set() 구현
6. [ ] search_repo_update_stats() 구현

**주의사항:**
- infra/core 모듈 import 없이 infra 직접 사용
- 비동기 함수로 구현
- 에러 처리 포함

### Day 3-4: 단일 기능 서비스 구현 (12월 15-16일)

#### 3-1. search_query_processor.py (Day 3 오전)
```python
class SearchQueryProcessor:
    # 질의 검증, 정규화, 필터 추출
```

**구현 체크리스트:**
- [ ] 350줄 이하 유지
- [ ] search_ 프리픽스 적용
- [ ] 자연어 필터 추출 로직
- [ ] 캐시 연동

#### 3-2. search_embedding_service.py (Day 3 오후)
```python
class SearchEmbeddingService:
    # OpenAI 임베딩 생성
    # 캐시 관리
```

**구현 체크리스트:**
- [ ] OpenAI API 연동
- [ ] 임베딩 캐시 구현
- [ ] 재시도 로직 추가
- [ ] 타임아웃 처리

#### 3-3. search_vector_service.py (Day 4 오전)
```python
class SearchVectorService:
    # Qdrant 검색
    # 다중 컬렉션 지원
    # 순수 벡터 검색 모드
```

**구현 체크리스트:**
- [ ] VectorStoreManager 활용
- [ ] 검색 모드별 분기 처리
- [ ] 다중 컬렉션 병렬 검색
- [ ] 점수 정규화 로직

#### 3-4. search_result_enricher.py (Day 4 오후)
```python
class SearchResultEnricher:
    # 메타데이터 보강
    # 스니펫 생성
```

**구현 체크리스트:**
- [ ] MongoDB 메타데이터 조회
- [ ] 검색어 하이라이팅
- [ ] 결과 포맷팅

### Day 5: 오케스트레이션 및 API 통합 (12월 17일)

#### 5-1. orchestrator.py 구현 (오전)
```python
class SearchOrchestrator:
    # 전체 프로세스 조율
    # 에러 처리
    # 성능 측정
```

**구현 순서:**
1. [ ] 서비스 초기화
2. [ ] search_orchestrator_process() 구현
3. [ ] 에러 처리 미들웨어
4. [ ] 로깅 및 모니터링

#### 5-2. API 통합 (오후)
**위치:** main/api_gateway.py

**추가할 엔드포인트:**
- [ ] POST /api/v1/search
- [ ] POST /api/v1/search/vector
- [ ] GET /api/v1/search/collections
- [ ] GET /api/v1/search/health

### Day 6: 테스트 및 최적화 (12월 18일)

#### 6-1. 시나리오 테스트 작성
**위치:** tests/scenario/

**작성할 테스트:**
- [ ] search_basic_scenario.py
- [ ] search_vector_only_scenario.py
- [ ] search_multi_collection_scenario.py
- [ ] search_performance_scenario.py

#### 6-2. 성능 최적화
- [ ] 캐시 히트율 측정
- [ ] 응답 시간 프로파일링
- [ ] 병목 지점 개선
- [ ] 메모리 사용량 최적화

## 🚨 위험 요소 및 대응 방안

### 1. OpenAI API 의존성
- **위험**: API 지연 또는 장애
- **대응**: 
  - 임베딩 캐시 강화 (TTL 1시간)
  - 재시도 로직 (최대 3회)
  - 타임아웃 설정 (5초)

### 2. Qdrant 성능
- **위험**: 대용량 검색 시 지연
- **대응**:
  - 결과 캐싱 (TTL 10분)
  - 비동기 병렬 검색
  - 인덱스 최적화

### 3. 다중 컬렉션 병합
- **위험**: 점수 정규화 복잡도
- **대응**:
  - 컬렉션별 가중치 적용
  - 상위 N개만 병합

## 📊 성능 목표 및 측정

### 목표 지표
| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 응답 시간 | < 1초 | 95 percentile |
| 캐시 히트율 | > 80% | Redis 통계 |
| 동시 처리 | > 50 req/s | 부하 테스트 |
| 메모리 사용 | < 500MB | 프로세스 모니터링 |

### 측정 도구
- OpenTelemetry Trace
- Redis 모니터링
- FastAPI 메트릭스

## 🔧 개발 환경 설정

### 필수 패키지 (pyproject.toml에 추가)
```toml
[project.dependencies]
pydantic = "^2.0"
redis = "^5.0"
motor = "^3.0"
openai = "^1.0"
qdrant-client = "^1.7"
```

### 환경 변수 (.env)
```bash
# 이미 설정됨 확인 필요
OPENAI_API_KEY=
QDRANT_URL=
MONGODB_URI=
REDIS_URL=
```

## ✅ 일별 완료 기준

### Day 1 완료 기준
- [ ] 모든 Pydantic 모델 정의
- [ ] 타입 체크 통과 (mypy)
- [ ] __init__.py 공개 인터페이스 정의

### Day 2 완료 기준
- [ ] Repository 클래스 구현
- [ ] DB/캐시 연동 테스트
- [ ] 비동기 처리 검증

### Day 3-4 완료 기준
- [ ] 4개 서비스 클래스 구현
- [ ] 각 파일 350줄 이하
- [ ] 단위 기능 동작 확인

### Day 5 완료 기준
- [ ] Orchestrator 구현
- [ ] API 엔드포인트 동작
- [ ] Swagger 문서 자동 생성

### Day 6 완료 기준
- [ ] 시나리오 테스트 통과
- [ ] 성능 목표 달성
- [ ] 문서화 완료

## 📝 코드 리뷰 체크리스트

### 아키텍쳐 준수
- [ ] 오케스트레이터 패턴 적용
- [ ] 단방향 의존성
- [ ] 파일당 350줄 이하

### 코드 품질
- [ ] search_ 프리픽스 일관성
- [ ] 타입 힌트 100%
- [ ] 에러 처리 완벽

### 성능
- [ ] 비동기 처리 적용
- [ ] 캐싱 전략 구현
- [ ] 병렬 처리 활용

## 🎯 최종 결과물

### 구현 파일
1. schema.py - 데이터 모델
2. repository.py - DB 접근
3. search_query_processor.py - 질의 처리
4. search_embedding_service.py - 임베딩
5. search_vector_service.py - 벡터 검색
6. search_result_enricher.py - 결과 보강
7. orchestrator.py - 프로세스 조율
8. __init__.py - 공개 인터페이스

### API 엔드포인트
- POST /api/v1/search
- POST /api/v1/search/vector
- GET /api/v1/search/collections
- GET /api/v1/search/health

### 테스트 시나리오
- 기본 검색 시나리오
- 순수 벡터 검색 시나리오
- 다중 컬렉션 시나리오
- 성능 테스트 시나리오

이 계획에 따라 진행하면 6일 내에 Search 모듈을 완성할 수 있습니다.
