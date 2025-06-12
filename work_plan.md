# IACSRAG 프로젝트 작업 계획서 (개발 단계)

## 1. 작업 개요

### 1.1 프로젝트 범위
- 9개 유즈케이스 구현 (UC-1 ~ UC-8, UC-1은 독립 검색 서비스)
- 9개 모듈 개발 (search, email, thread, participant, deadline, completion, issue, dashboard, validation)
- 인프라 및 공통 컴포넌트 구축
- 시나리오 테스트 및 기본 배포 준비

### 1.2 작업 원칙 (개발 단계)
- **오케스트레이터 패턴** 적용으로 모듈간 호출 순서 통제
- **단순한 직접 호출** 방식으로 복잡성 제거
- **데이터 계약 우선** 설계로 모듈간 인터페이스 사전 정의
- **시나리오 테스트** 기반 검증 (단위/통합 테스트 제외)
- **최소 기능 구현** 우선, 고급 기능은 프로덕션 단계에서 고려

## 2. 단계별 작업 계획

### Phase 1: 기반 인프라 구축 (Foundation)
**목표**: 모든 모듈이 공통으로 사용할 인프라 컴포넌트 구축

#### 1.1 프로젝트 초기 설정
- **작업**: 프로젝트 구조 생성, 환경 설정
- **산출물**: 
  - `pyproject.toml` (uv 패키지 관리)
  - `.env` 환경 변수 파일
  - `docker-compose.yml` 외부 서비스 설정 (MongoDB, Qdrant, Redis만)
  - 기본 디렉토리 구조 생성
- **의존성**: 없음
- **우선순위**: 최고

#### 1.2 인프라 코어 모듈 구현
- **작업**: `infra/core/` 패키지 구현
- **산출물**:
  - `database.py`: MongoDB 연결 및 세션 관리
  - `vector_store.py`: Qdrant 클라이언트 및 컬렉션 관리
  - `cache.py`: Redis 캐시 관리 (message_broker.py 대체)
  - `config.py`: 전역 설정 및 환경변수 관리
- **의존성**: 1.1 완료
- **우선순위**: 최고

#### 1.3 공통 스키마 정의(사용하지 않음)

#### 1.4 로깅 설정
- **작업**: 기본 로깅 구성 (OpenTelemetry는 선택사항)
- **산출물**:
  - `infra/core/logging.py`: 구조화된 로깅 설정
- **의존성**: 1.2 완료
- **우선순위**: 보통

### Phase 2: 독립 검색 서비스 (Search Service)
**목표**: Qdrant 벡터 검색 서비스 구축

#### 2.1 Search 모듈 (벡터 검색) - UC-1
- **작업**: 자연어 질의 기반 벡터 검색 서비스
- **산출물**:
  - `modules/search/schema.py`: SearchQuery, SearchResults 모델
  - `modules/search/repository.py`: Qdrant/MongoDB 연동
  - `modules/search/search_service.py`: 벡터 검색 서비스
  - `modules/search/search_query.py`: 질의 처리 서비스
  - `modules/search/orchestrator.py`: 검색 처리 오케스트레이터
- **의존성**: Phase 1 완료, 기존 Qdrant 데이터 필요
- **우선순위**: 높음
- **검증**: `/tests/scenario/search_service_scenario.py`

### Phase 3: 데이터 처리 모듈 (Data Ingestion)
**목표**: 이메일 수집과 기본 처리 파이프라인 구축

#### 3.1 Thread 모듈 (스레드 관리) - UC-2
- **작업**: 제목 프리픽스 기반 스레드 분류 및 관리
- **산출물**:
  - `modules/thread/schema.py`: ThreadData, ThreadStatus 모델
  - `modules/thread/repository.py`: 스레드 데이터 CRUD
  - `modules/thread/thread_classifier.py`: 스레드 분류 서비스
  - `modules/thread/thread_manager.py`: 스레드 생성/업데이트 서비스
  - `modules/thread/orchestrator.py`: 스레드 처리 오케스트레이터
- **의존성**: 3.1 완료 (이메일 데이터 필요)
- **우선순위**: 최고
- **검증**: `/tests/scenario/thread_classification_scenario.py`

### Phase 4: 참여자 및 상태 관리 모듈 (Participant Management)
**목표**: 참여자 추적 및 상태 관리 시스템 구축

#### 4.1 Participant 모듈 (참여자 관리) - UC-3
- **작업**: 참여자 역할 매핑 및 상태 추적
- **산출물**:
  - `modules/participant/schema.py`: ParticipantData, ParticipantRole 모델
  - `modules/participant/repository.py`: 참여자 데이터 관리
  - `modules/participant/participant_tracker.py`: 참여자 상태 추적 서비스
  - `modules/participant/participant_mapper.py`: 역할 매핑 서비스
  - `modules/participant/orchestrator.py`: 참여자 처리 오케스트레이터
- **의존성**: 3.2 완료 (스레드 정보 필요)
- **우선순위**: 높음
- **검증**: `/tests/scenario/participant_tracking_scenario.py`

#### 4.2 Deadline 모듈 (마감일 관리) - UC-4
- **작업**: 마감일 모니터링 및 기본 알림 시스템
- **산출물**:
  - `modules/deadline/schema.py`: DeadlinePolicy, OverdueParticipant 모델
  - `modules/deadline/repository.py`: 마감일 데이터 관리
  - `modules/deadline/deadline_watcher.py`: 마감일 모니터링 서비스
  - `modules/deadline/deadline_notifier.py`: 기본 로그 알림 (이메일 알림 선택사항)
  - `modules/deadline/orchestrator.py`: 마감일 처리 오케스트레이터
- **의존성**: 4.1 완료 (참여자 상태 필요)
- **우선순위**: 높음
- **검증**: `/tests/scenario/deadline_monitoring_scenario.py`

### Phase 5: 분석 및 완료 처리 모듈 (Analysis & Completion)
**목표**: 완료 판정 및 이슈 분석 기능 구현

#### 5.1 Completion 모듈 (완료 판정) - UC-5
- **작업**: 스레드 완료 조건 판정 및 처리
- **산출물**:
  - `modules/completion/schema.py`: CompletionResult, SentimentResult 모델
  - `modules/completion/repository.py`: 완료 상태 데이터 관리
  - `modules/completion/completion_engine.py`: 완료 판정 엔진
  - `modules/completion/completion_detector.py`: 완료 조건 감지 서비스
  - `modules/completion/orchestrator.py`: 완료 처리 오케스트레이터
- **의존성**: 4.2 완료 (참여자 상태, 마감일 정보 필요)
- **우선순위**: 보통
- **검증**: `/tests/scenario/completion_detection_scenario.py`

#### 5.2 Issue 모듈 (이슈 분석) - UC-6
- **작업**: 의미적 이슈 추출 및 태깅
- **산출물**:
  - `modules/issue/schema.py`: IssueTag, SentimentType 모델
  - `modules/issue/repository.py`: 이슈 데이터 관리
  - `modules/issue/issue_extractor.py`: 이슈 추출 서비스
  - `modules/issue/issue_tagger.py`: 태깅 처리 서비스
  - `modules/issue/orchestrator.py`: 이슈 분석 오케스트레이터
- **의존성**: 3.1 완료 (이메일 임베딩 필요), OpenAI API 연동
- **우선순위**: 보통
- **검증**: `/tests/scenario/issue_extraction_scenario.py`

### Phase 6: 사용자 인터페이스 모듈 (User Interface)
**목표**: 대시보드, 검증 기능 구현

#### 6.1 Dashboard 모듈 (대시보드) - UC-7
- **작업**: 기본 대시보드 및 검색 인터페이스
- **산출물**:
  - `modules/dashboard/schema.py`: DashboardData, SearchQuery 모델
  - `modules/dashboard/repository.py`: 대시보드 데이터 집계
  - `modules/dashboard/dashboard_service.py`: 대시보드 API 서비스
  - `modules/dashboard/dashboard_search.py`: 기본 검색 서비스
  - `modules/dashboard/orchestrator.py`: 대시보드 오케스트레이터
- **의존성**: Phase 3-5 대부분 완료 (모든 데이터 필요)
- **우선순위**: 보통
- **검증**: `/tests/scenario/dashboard_interface_scenario.py`

#### 6.2 Validation 모듈 (형식 검사) - UC-8
- **작업**: 이메일 형식 검증 및 기본 정정 제안
- **산출물**:
  - `modules/validation/schema.py`: ValidationResult, Correction 모델
  - `modules/validation/repository.py`: 검증 규칙 관리
  - `modules/validation/validation_checker.py`: 형식 검증 서비스
  - `modules/validation/validation_corrector.py`: 기본 정정 제안 서비스
  - `modules/validation/orchestrator.py`: 검증 처리 오케스트레이터
- **의존성**: 2.1 완료 (이메일 데이터 필요)
- **우선순위**: 낮음
- **검증**: `/tests/scenario/validation_scenario.py`

### Phase 6: 통합 및 배포 준비 (Integration & Deployment)
**목표**: 전체 시스템 통합 및 기본 배포 준비

#### 6.1 메인 오케스트레이터 구현
- **작업**: 전체 시스템 조율하는 메인 오케스트레이터
- **산출물**:
  - `main/main_orchestrator.py`: 전체 시스템 오케스트레이터 (직접 호출 방식)
  - `main/api_gateway.py`: FastAPI 기반 API 게이트웨이
- **의존성**: Phase 2-5 완료
- **우선순위**: 높음

#### 6.2 시나리오 테스트 구현
- **작업**: 전체 시스템 검증을 위한 시나리오 테스트
- **산출물**:
  - `/tests/scenario/end_to_end_scenario.py`: 전체 플로우 테스트
  - `/tests/scenario/basic_performance_scenario.py`: 기본 성능 검증 테스트
  - `/tests/scenario/error_handling_scenario.py`: 에러 처리 테스트
- **의존성**: 6.1 완료
- **우선순위**: 높음

#### 6.3 기본 배포 환경 구성
- **작업**: 개발/테스트 배포를 위한 환경 구성
- **산출물**:
  - `docker/Dockerfile`: 애플리케이션 도커 이미지
  - `docker/docker-compose.dev.yml`: 개발 환경 구성
  - `docs/setup_guide.md`: 설정 가이드 문서
- **의존성**: 6.2 완료
- **우선순위**: 보통

## 3. 모듈간 의존성 관계 (단순화)

### 3.1 의존성 다이어그램
```
infra/core (기반)
    ↓
email (UC-1) → thread (UC-2) → participant (UC-3) → deadline (UC-4) → completion (UC-5)
    ↓              ↓                  ↓              
issue (UC-6) ←─────┴──────────────────┘              
    ↓                              
dashboard (UC-7) ←─────────────────────────────────────────────┘
    ↓
validation (UC-8) ←─────────────────────────────────────────────┘
    ↓
main/orchestrator (통합) - 직접 함수 호출 방식
```

### 3.2 데이터 흐름 의존성 (단순화)
- **email → thread**: 이메일 데이터 → 스레드 분류 (함수 직접 호출)
- **thread → participant**: 스레드 정보 → 참여자 매핑 (함수 직접 호출)
- **participant → deadline**: 참여자 상태 → 마감일 모니터링 (함수 직접 호출)
- **deadline → completion**: 마감일 정보 → 완료 판정 (함수 직접 호출)
- **email → issue**: 이메일 임베딩 → 이슈 분석 (함수 직접 호출)
- **all → dashboard**: 모든 데이터 → 대시보드 집계 (DB 조회)
- **email → validation**: 이메일 형식 → 검증 (함수 직접 호출)

## 4. 마일스톤 및 검증 기준

### Milestone 1: 기반 인프라 (Phase 1)
**완료 기준**:
- [ ] 외부 서비스 (MongoDB, Qdrant, Redis) 연결 확인
- [ ] 기본 로깅 기능 동작 확인
- [ ] 환경 설정 및 Docker 컨테이너 정상 실행
- [ ] 공통 스키마 정의 완료

**검증 방법**:
- 연결 테스트 스크립트 실행
- 기본 CRUD 동작 확인
- 로그 출력 확인

### Milestone 2: 데이터 파이프라인 (Phase 2)
**완료 기준**:
- [ ] Microsoft Graph API에서 이메일 수집 성공
- [ ] 이메일 임베딩 생성 및 Qdrant 저장 성공
- [ ] 제목 프리픽스 추출 및 스레드 분류 성공
- [ ] Redis 캐시를 통한 상태 관리 확인

**검증 방법**:
- `email_collection_scenario.py` 실행
- `thread_classification_scenario.py` 실행
- 데이터베이스 저장 상태 확인

### Milestone 3: 상태 관리 (Phase 3)
**완료 기준**:
- [ ] 참여자 역할 매핑 및 상태 추적 성공
- [ ] 마감일 계산 및 오버듀 감지 성공
- [ ] 기본 알림 로그 기록 확인
- [ ] 참여자 맵 업데이트 확인

**검증 방법**:
- `participant_tracking_scenario.py` 실행
- `deadline_monitoring_scenario.py` 실행
- 알림 로그 확인

### Milestone 4: 분석 및 완료 (Phase 4)
**완료 기준**:
- [ ] 완료 조건 감지 및 스레드 종료 성공
- [ ] 이슈 태그 자동 분류 성공
- [ ] 기본 검색 기능 동작 확인
- [ ] LLM 기반 감정 분석 결과 확인

**검증 방법**:
- `completion_detection_scenario.py` 실행
- `issue_extraction_scenario.py` 실행
- 검색 기능 검증

### Milestone 5: 사용자 인터페이스 (Phase 5)
**완료 기준**:
- [ ] 대시보드 API 기본 엔드포인트 동작
- [ ] 기본 검색 인터페이스 동작
- [ ] 데이터 조회 기능 동작
- [ ] 형식 검증 및 기본 정정 제안 동작

**검증 방법**:
- `dashboard_interface_scenario.py` 실행
- `validation_scenario.py` 실행
- API 응답 확인

### Milestone 6: 시스템 통합 (Phase 6)
**완료 기준**:
- [ ] 전체 시스템 End-to-End 플로우 성공
- [ ] 기본 성능 요구사항 만족 (초당 50개 이메일 처리)
- [ ] 에러 처리 기능 동작
- [ ] 개발 환경 구성 완료

**검증 방법**:
- `end_to_end_scenario.py` 실행
- `basic_performance_scenario.py` 실행
- 기본 안정성 테스트

## 5. 기술적 고려사항 (개발 단계)

### 5.1 개발 환경 설정
- **Python**: 3.11+
- **패키지 관리**: uv (pyproject.toml)
- **비동기 프레임워크**: FastAPI + asyncio
- **데이터 검증**: Pydantic v2
- **외부 연동**: Microsoft Graph SDK, OpenAI API

### 5.2 성능 최적화 포인트 (기본)
- **배치 처리**: 이메일 수집 시 25개씩 배치 처리
- **비동기 처리**: 모든 I/O 작업 비동기화
- **캐싱**: Redis를 활용한 기본 데이터 캐싱
- **인덱싱**: MongoDB 기본 인덱스 설계

### 5.3 에러 처리 전략 (단순화)
- **재시도 로직**: 외부 API 호출 실패 시 간단한 재시도
- **부분 실패 허용**: 모듈 실패 시 로그 기록 후 계속 진행
- **알림 시스템**: 중요 에러 발생 시 로그 기록

### 5.4 모니터링 및 로깅 (기본)
- **구조화된 로깅**: JSON 형식으로 기본 로그 출력
- **기본 추적**: 요청 ID를 통한 간단한 추적
- **헬스체크**: 각 모듈별 기본 헬스체크

## 6. 리스크 및 대응 방안

### 6.1 기술적 리스크
| 리스크 | 확률 | 영향도 | 대응 방안 |
|--------|------|--------|-----------|
| Microsoft Graph API 제한 | 높음 | 높음 | 요청 제한 모니터링, 배치 크기 조정 |
| OpenAI API 비용 증가 | 보통 | 중간 | 임베딩 캐싱, 사용량 모니터링 |
| Qdrant 성능 이슈 | 낮음 | 중간 | 기본 인덱스 최적화 |
| 데이터 형식 변경 | 보통 | 보통 | 스키마 버전 관리 |

### 6.2 비즈니스 리스크
| 리스크 | 확률 | 영향도 | 대응 방안 |
|--------|------|--------|-----------|
| 요구사항 변경 | 높음 | 보통 | 모듈화 설계로 변경 영향 최소화 |
| 성능 요구사항 미달 | 보통 | 보통 | 기본 성능 테스트 실시 |
| 개발 일정 지연 | 중간 | 높음 | 단계별 마일스톤 관리 |

### 6.3 운영 리스크
| 리스크 | 확률 | 영향도 | 대응 방안 |
|--------|------|--------|-----------|
| 시스템 장애 | 보통 | 중간 | 기본 재시작 메커니즘 |
| 데이터 손실 | 낮음 | 높음 | 기본 백업, 데이터 검증 |
| 의존성 서비스 장애 | 보통 | 중간 | 기본 에러 처리, 재시도 로직 |

## 7. 품질 보증 계획 (개발 단계)

### 7.1 코드 품질 관리
- **코드 리뷰**: 주요 기능에 대해 코드 리뷰 실시
- **정적 분석**: mypy, ruff를 활용한 기본 정적 분석
- **문서화**: 각 모듈별 기본 README.md 작성

### 7.2 테스트 전략
- **시나리오 테스트**: 실제 사용 시나리오 기반 테스트만 구현
- **기본 통합 테스트**: 모듈간 인터페이스 테스트 (API 레벨)
- **기본 성능 테스트**: 응답 시간 및 처리량 측정

### 7.3 배포 및 릴리즈
- **개발 환경**: Docker 기반 개발 환경 구성
- **기본 배포**: 단순한 컨테이너 기반 배포
- **모니터링**: 기본 로그 기반 모니터링

## 8. 성공 기준 및 완료 조건 (개발 단계)

### 8.1 기능적 성공 기준
- [ ] 8개 유즈케이스 모두 기본 기능 구현 완료
- [ ] 모든 시나리오 테스트 통과
- [ ] 기본 API 문서 완성
- [ ] 개발 환경 배포 성공

### 8.2 비기능적 성공 기준
- [ ] 이메일 처리 속도: 초당 50개 이상
- [ ] 검색 응답 시간: 1초 이하
- [ ] 시스템 가용성: 95% 이상 (개발 환경)
- [ ] 메모리 사용량: 2GB 이하

### 8.3 운영 준비도 기준
- [ ] 기본 모니터링 로그 구축 완료
- [ ] 기본 알림 프로세스 구축
- [ ] 백업 절차 문서화
- [ ] 개발팀 사용법 교육 완료

## 9. 개발 단계 특별 고려사항

### 9.1 단순화 원칙
- **직접 호출**: 모듈간 복잡한 메시징 대신 직접 함수 호출
- **기본 기능**: 고급 기능보다 핵심 기능 우선 구현
- **최소 의존성**: 필수 외부 서비스만 사용

### 9.2 확장성 고려
- **인터페이스 일관성**: 향후 확장 가능한 인터페이스 설계
- **데이터 모델**: 확장 가능한 데이터 모델 설계
- **모듈 분리**: 명확한 모듈 경계 유지

### 9.3 개발 효율성
- **코드 재사용**: 공통 컴포넌트 최대 활용
- **템플릿 활용**: 모듈별 코드 템플릿 사용
- **점진적 구현**: 기본 기능부터 점진적 확장

이 작업 계획서는 개발 단계에 특화되어 복잡성을 줄이고 핵심 기능 구현에 집중할 수 있도록 설계되었습니다. Message Broker와 Kafka 등 복잡한 인프라는 제거하고, 직접 함수 호출을 통한 단순한 아키텍쳐로 구성하여 개발 속도를 높이고 유지보수를 용이하게 했습니다.
