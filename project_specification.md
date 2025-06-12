# IACSRAG 프로젝트 상세 명세서

## 1. 프로젝트 개요

### 1.1 프로젝트명
IACSRAG (International Association Correspondence Search & Reporting Analysis Gateway)

### 1.2 목적
Qdrant 벡터 DB와 이메일 메타데이터를 활용한 "의장-멤버 코레스폰던스" 프로세스 모니터링 및 자동화 시스템

### 1.3 주요 기능
- 자연어 질의 기반 벡터 검색 서비스
- 기존 Qdrant 벡터 DB의 이메일 데이터 활용
- 스레드 기반 주제 관리
- 참여자 상태 추적 및 모니터링
- 마감일 기반 자동 알림
- 의미적 검색 및 이슈 태깅
- 실시간 대시보드 제공

## 2. 아키텍쳐 설계 (개발 단계)

### 2.1 전체 시스템 아키텍쳐
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   Core Engine   │
│   Dashboard     │◄──►│                 │◄──►│                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │   Data Layer    │
                                               │                 │
                                               └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │  MongoDB        │
                                               │  Qdrant (기존)  │
                                               │  Redis (Cache)  │
                                               └─────────────────┘
```

### 2.2 모듈 구조 (프로젝트 아키텍쳐 지침 준수)
```
iacsrag/
├── infra/
│   ├── core/                    # 공통 인프라
│   │   ├── __init__.py
│   │   ├── database.py          # DB 연결 관리
│   │   ├── vector_store.py      # Qdrant 연결 관리
│   │   ├── cache.py            # Redis 캐시 관리
│   │   └── config.py           # 전역 설정
│   └── docker/                 # 도커 설정
├── modules/
│   ├── search/                 # 벡터 검색 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 검색 처리 오케스트레이터
│   │   ├── search_service.py   # UC-1: Qdrant 벡터 검색
│   │   ├── search_query.py     # 질의 처리
│   │   ├── repository.py       # Qdrant/MongoDB 연동
│   │   └── schema.py          # Pydantic 모델
│   ├── email/                  # 이메일 처리 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 이메일 처리 오케스트레이터
│   │   ├── email_collector.py  # UC-2: 이메일 수집
│   │   ├── email_embedding.py  # 임베딩 처리
│   │   ├── repository.py       # DB/API 처리
│   │   └── schema.py          # Pydantic 모델
│   ├── thread/                 # 스레드 관리 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 스레드 처리 오케스트레이터
│   │   ├── thread_classifier.py # UC-2: 스레드 분류
│   │   ├── thread_manager.py   # 스레드 생성/관리
│   │   ├── repository.py
│   │   └── schema.py
│   ├── participant/            # 참여자 관리 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 참여자 처리 오케스트레이터
│   │   ├── participant_tracker.py # UC-3: 참여자 추적
│   │   ├── participant_mapper.py # 역할 매핑
│   │   ├── repository.py
│   │   └── schema.py
│   ├── deadline/               # 마감일 관리 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 마감일 처리 오케스트레이터
│   │   ├── deadline_watcher.py # UC-4: 마감일 모니터링
│   │   ├── deadline_notifier.py # 알림 발송
│   │   ├── repository.py
│   │   └── schema.py
│   ├── completion/             # 완료 판정 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 완료 판정 오케스트레이터
│   │   ├── completion_engine.py # UC-5: 완료 판정
│   │   ├── completion_detector.py # 완료 조건 감지
│   │   ├── repository.py
│   │   └── schema.py
│   ├── issue/                  # 이슈 분석 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 이슈 분석 오케스트레이터
│   │   ├── issue_extractor.py  # UC-6: 이슈 추출
│   │   ├── issue_tagger.py     # 태깅 처리
│   │   ├── repository.py
│   │   └── schema.py
│   ├── dashboard/              # 대시보드 모듈
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # 대시보드 오케스트레이터
│   │   ├── dashboard_service.py # UC-7: 대시보드 서비스
│   │   ├── dashboard_search.py # 검색 서비스
│   │   ├── repository.py
│   │   └── schema.py
│   └── validation/             # 형식 검사 모듈
│       ├── __init__.py
│       ├── orchestrator.py     # 검증 처리 오케스트레이터
│       ├── validation_checker.py # UC-8: 형식 검사
│       ├── validation_corrector.py # 자동 정정
│       ├── repository.py
│       └── schema.py
├── main/
│   ├── __init__.py
│   ├── main_orchestrator.py    # 메인 오케스트레이터
│   └── api_gateway.py          # API 게이트웨이
├── tests/
│   └── scenario/               # 시나리오 테스트만 구현
└── docs/
    ├── README.md
    └── api_docs.md
```

## 3. 유즈케이스별 상세 설계

### 3.1 UC-1: Qdrant 벡터 검색 서비스 (search 모듈)

**클래스 설계:**
```python
# search/search_service.py
class SearchService:
    def __init__(self, vector_store: VectorStore, llm_client: LLMClient, cache: CacheService)
    async def search_process_query(self, query: str, filters: Optional[SearchFilters] = None) -> SearchResults
    async def _search_create_query_embedding(self, query: str) -> List[float]
    async def _search_vector_search(self, embedding: List[float], filters: SearchFilters) -> List[VectorMatch]

# search/search_query.py
class SearchQueryProcessor:
    def __init__(self, repo: SearchRepository, cache: CacheService)
    async def search_query_validate_input(self, query: str) -> ValidationResult
    async def search_query_preprocess(self, query: str) -> ProcessedQuery
    async def _search_query_extract_filters(self, query: str) -> SearchFilters
```

**데이터 흐름:**
1. 사용자 자연어 질의 수신
2. 질의 전처리 및 검증
3. OpenAI API로 질의 임베딩 생성
4. Qdrant에서 유사도 검색 (score > 0.7)
5. MongoDB에서 메타데이터 보강
6. 검색 결과 랭킹 및 포맷팅
7. 검색 로그 기록

### 3.2 UC-2: 이메일 수집 및 임베딩 (email 모듈)

**클래스 설계:**
```python
# email/email_collector.py
class EmailCollectorService:
    def __init__(self, repo: EmailRepository, cache: CacheService)
    async def email_coll_collect_emails(self) -> List[EmailData]
    async def _email_coll_process_single_email(self, email: RawEmail) -> EmailData
    async def _email_coll_validate_email_format(self, email: RawEmail) -> bool

# email/email_embedding.py  
class EmailEmbeddingService:
    def __init__(self, vector_store: VectorStore, cache: CacheService)
    async def email_embd_create_embeddings(self, email: EmailData) -> EmbeddingResult
    async def _email_embd_extract_text_parts(self, email: EmailData) -> TextParts
    async def _email_embd_store_vectors(self, vectors: MultiVector) -> str
```

**데이터 흐름:**
1. Microsoft Graph API → Raw Email Data
2. Email Validation & Parsing → Structured EmailData
3. Text Extraction (Subject + Body) → TextParts
4. Embedding Generation → MultiVector (subject, body)
5. Qdrant Storage → Vector ID
6. MongoDB Storage → Document ID
7. Redis Cache Update → 처리 상태

### 3.2 UC-2: 스레드 분류 및 관리 (thread 모듈)

**클래스 설계:**
```python
# thread/thread_classifier.py
class ThreadClassifierService:
    def __init__(self, repo: ThreadRepository, cache: CacheService)
    async def thread_clsf_extract_subject_prefix(self, subject: str) -> Optional[str]
    async def thread_clsf_find_existing_thread(self, prefix: str) -> Optional[ThreadData]
    async def thread_clsf_create_new_thread(self, prefix: str, email: EmailData) -> ThreadData

# thread/thread_manager.py
class ThreadManagerService:
    def __init__(self, repo: ThreadRepository, cache: CacheService)
    async def thread_mgnt_update_thread_status(self, thread_id: str, status: ThreadStatus)
    async def thread_mgnt_add_email_to_thread(self, thread_id: str, email_id: str)
```

**비즈니스 규칙:**
- 제목 프리픽스 정규식: `^([A-Z]{2,4}\d{3,6})`
- 프리픽스가 없는 경우 "UNKNOWN" 스레드로 분류
- 스레드 상태: ACTIVE, PENDING, CLOSED, EXPIRED

### 3.3 UC-3: 참여자 추적 (participant 모듈)

**클래스 설계:**
```python
# participant/participant_tracker.py
class ParticipantTrackerService:
    def __init__(self, repo: ParticipantRepository, cache: CacheService)
    async def participant_trkr_update_participation_map(self, thread_id: str, email: EmailData)
    async def participant_trkr_resolve_participant_role(self, email_address: str) -> ParticipantRole
    async def _participant_trkr_mark_participant_active(self, thread_id: str, participant_id: str)

# participant/participant_mapper.py  
class ParticipantMapperService:
    def __init__(self, repo: ParticipantRepository, cache: CacheService)
    async def participant_mapr_get_organization_mapping(self) -> Dict[str, ParticipantRole]
    async def participant_mapr_update_role_mapping(self, email: str, role: ParticipantRole)
```

**참여자 상태:**
- ✅ RESPONDED: 회신 완료
- ❌ PENDING: 회신 대기
- ⏰ OVERDUE: 마감일 초과
- ❓ UNKNOWN: 미등록 참여자

### 3.4 UC-4: 마감일 모니터링 (deadline 모듈)

**클래스 설계:**
```python
# deadline/deadline_watcher.py
class DeadlineWatcherService:
    def __init__(self, repo: DeadlineRepository, notifier: DeadlineNotifierService, cache: CacheService)
    async def deadline_wtch_check_overdue_participants(self) -> List[OverdueParticipant]
    async def deadline_wtch_calculate_deadline(self, thread: ThreadData) -> datetime
    async def _deadline_wtch_get_deadline_policy(self, thread_type: str) -> DeadlinePolicy

# deadline/deadline_notifier.py
class DeadlineNotifierService:
    def __init__(self, email_client: EmailClient)
    async def deadline_ntfy_send_reminder_email(self, participant: OverdueParticipant)
    async def deadline_ntfy_log_notification(self, notification: NotificationLog)
```

**마감일 정책:**
- 일반 안건: 수신일 + 7일
- 긴급 안건: 수신일 + 3일  
- 최종 확인: 수신일 + 14일

### 3.5 UC-5: 완료 판정 (completion 모듈)

**클래스 설계:**
```python
# completion/completion_engine.py
class CompletionEngineService:
    def __init__(self, repo: CompletionRepository, cache: CacheService)
    async def completion_engn_check_completion_conditions(self, thread_id: str) -> CompletionResult
    async def completion_engn_process_chair_final_email(self, email: EmailData) -> bool
    async def _completion_engn_verify_all_participants_responded(self, thread_id: str) -> bool

# completion/completion_detector.py
class CompletionDetectorService:
    def __init__(self, repo: CompletionRepository)
    async def completion_dtct_detect_final_email_pattern(self, subject: str, body: str) -> bool
    async def completion_dtct_analyze_completion_sentiment(self, body: str) -> SentimentResult
```

**완료 조건:**
1. 의장 최종 이메일 (제목에 "Final", "Closed", "Complete" 포함)
2. 모든 필수 참여자 회신 완료
3. 명시적 종료 명령

### 3.6 UC-6: 이슈 분석 (issue 모듈)

**클래스 설계:**
```python
# issue/issue_extractor.py
class IssueExtractorService:
    def __init__(self, vector_store: VectorStore, llm_client: LLMClient, cache: CacheService)
    async def issue_extr_extract_semantic_issues(self, email: EmailData) -> List[IssueTag]
    async def issue_extr_classify_sentiment(self, text: str) -> SentimentType
    async def _issue_extr_find_similar_issues(self, embedding: List[float]) -> List[SimilarIssue]

# issue/issue_tagger.py
class IssueTaggerService:
    def __init__(self, repo: IssueRepository, cache: CacheService)
    async def issue_tagr_apply_tags_to_email(self, email_id: str, tags: List[IssueTag])
    async def issue_tagr_update_issue_statistics(self, thread_id: str, tags: List[IssueTag])
```

**이슈 태그 유형:**
- 🚨 RISK: 위험 요소 감지
- ❌ OBJECTION: 반대 의견
- ✅ AGREEMENT: 동의 표현
- ❓ QUESTION: 질문/확인 요청
- 📋 REQUIREMENT: 요구사항 변경

### 3.7 UC-7: 대시보드 (dashboard 모듈)

**클래스 설계:**
```python
# dashboard/dashboard_service.py
class DashboardServiceAPI:
    def __init__(self, repo: DashboardRepository, search: DashboardSearchService, cache: CacheService)
    async def dashboard_serv_get_dashboard_data(self, user_id: str) -> DashboardData
    async def dashboard_serv_get_thread_statistics(self, filters: DashboardFilters) -> ThreadStats
    async def dashboard_serv_export_data(self, format: ExportFormat) -> ExportResult

# dashboard/dashboard_search.py
class DashboardSearchService:
    def __init__(self, vector_store: VectorStore, mongo_client: MongoClient, cache: CacheService)
    async def dashboard_srch_hybrid_search(self, query: SearchQuery) -> SearchResults
    async def dashboard_srch_filter_by_metadata(self, filters: MetadataFilters) -> List[EmailData]
```

**대시보드 위젯:**
- 스레드 상태 분포 차트
- 참여율 히트맵
- 오버듀 알림 목록
- 이슈 태그 트렌드
- 실시간 검색 인터페이스

### 3.8 UC-8: 형식 검사 (validation 모듈)

**클래스 설계:**
```python
# validation/validation_checker.py
class ValidationCheckerService:
    def __init__(self, repo: ValidationRepository, cache: CacheService)
    async def validation_chck_validate_email_format(self, email: EmailData) -> ValidationResult
    async def validation_chck_check_subject_pattern(self, subject: str) -> PatternResult
    async def _validation_chck_apply_format_rules(self, email: EmailData) -> List[ValidationError]

# validation/validation_corrector.py
class ValidationCorrectorService:
    def __init__(self, email_client: EmailClient, repo: ValidationRepository)
    async def validation_corr_send_correction_notice(self, email: EmailData, errors: List[ValidationError])
    async def validation_corr_suggest_corrections(self, email: EmailData) -> List[Correction]
```

**검증 규칙:**
- 제목 프리픽스 형식: `[PREFIX]` 
- 필수 참여자 포함 여부
- 첨부파일 형식 제한
- 보안 분류 표시

## 4. 데이터 모델 설계

### 4.1 MongoDB 컬렉션 스키마

```python
# 공통 스키마 (모든 모듈의 schema.py에서 공유)
class EmailData(BaseModel):
    id: str = Field(alias="_id")
    graph_email_id: str
    subject: str
    subjectprefix: Optional[str]
    sender_name: str
    sender_address: str
    recipients: RecipientsData
    body: EmailBody
    has_attachments: bool
    received_date: datetime
    processed_at: datetime
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime

class ThreadData(BaseModel):
    id: str = Field(alias="_id")
    subjectprefix: str
    status: ThreadStatus
    chair_id: str
    participants: List[ParticipantData]
    deadline: datetime
    email_count: int = 0
    created_at: datetime
    closed_at: Optional[datetime]

class ParticipantData(BaseModel):
    email_address: str
    name: str
    role: ParticipantRole
    status: ParticipantStatus
    last_response_date: Optional[datetime]
    notification_count: int = 0
```

### 4.2 Qdrant 벡터 스키마

```python
class EmailVectorPayload(BaseModel):
    document_id: str
    subjectprefix: str
    subject: str
    body: str
    sender_name: str
    sender_address: str
    recipients: dict
    has_attachments: bool
    received_date: str
    issue_tags: List[str] = []
    thread_id: Optional[str]
    processing_status: str
```

### 4.3 처리 상태 관리

```python
class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EMBEDDING_CREATED = "embedding_created"
    THREAD_ASSIGNED = "thread_assigned"
    PARTICIPANTS_MAPPED = "participants_mapped"
    ISSUES_ANALYZED = "issues_analyzed"
    COMPLETED = "completed"
    FAILED = "failed"
```

## 5. 외부 시스템 연동

### 5.1 Microsoft Graph API
- 엔드포인트: `/v1.0/me/messages`
- 인증: OAuth 2.0
- 요청 제한: 분당 10,000회
- 배치 크기: 50개

### 5.2 데이터베이스 연결
- **MongoDB**: 메타데이터, 스레드 정보, 참여자 데이터
- **Qdrant**: 이메일 임베딩 벡터, 유사도 검색
- **Redis**: 세션 캐시, 처리 상태 관리

### 5.3 외부 서비스
- **OpenAI API**: 텍스트 임베딩 생성
- **SMTP 서버**: 알림 이메일 발송  
- **웹 대시보드**: FastAPI 기반 API 서버

## 6. 오케스트레이션 설계

### 6.1 메인 오케스트레이터 플로우
```python
class MainOrchestrator:
    async def process_email_pipeline(self, email_id: str):
        # 1. 이메일 수집 및 임베딩
        email_data = await self.email_orchestrator.process_email(email_id)
        
        # 2. 스레드 분류 및 할당
        thread_data = await self.thread_orchestrator.classify_and_assign(email_data)
        
        # 3. 참여자 상태 업데이트
        participants = await self.participant_orchestrator.update_participants(thread_data, email_data)
        
        # 4. 마감일 확인 및 알림
        await self.deadline_orchestrator.check_deadlines(thread_data.id)
        
        # 5. 완료 조건 확인
        completion_status = await self.completion_orchestrator.check_completion(thread_data.id)
        
        # 6. 이슈 분석 및 태깅
        await self.issue_orchestrator.analyze_issues(email_data)
        
        return completion_status
```

### 6.2 모듈간 직접 호출 방식
- 비동기 함수 직접 호출로 복잡성 제거
- 캐시를 통한 성능 최적화
- 명시적 에러 처리 및 로깅

## 7. 성능 및 확장성

### 7.1 성능 목표
- 이메일 처리 속도: 초당 50개 (개발 단계)
- 검색 응답 시간: 1초 이하
- 대시보드 로딩: 3초 이하
- 동시 사용자: 10명

### 7.2 개발 단계 최적화
- Redis 캐싱으로 중복 처리 방지
- 배치 처리로 DB 부하 감소
- 비동기 처리로 I/O 대기 시간 최소화

### 7.3 모니터링
- OpenTelemetry 분산 추적
- 구조화된 로깅
- 기본 헬스체크 엔드포인트

## 8. 보안 고려사항

### 8.1 데이터 보안
- 환경변수를 통한 민감 정보 관리
- 기본적인 입력값 검증
- MongoDB 연결 암호화

### 8.2 API 보안
- 기본 인증 구현
- Rate Limiting 적용
- HTTPS 사용 권장

### 8.3 시스템 보안
- Docker 컨테이너 기반 격리
- 기본 백업 정책
- 로그 기반 모니터링

## 9. 개발 단계 제약사항

### 9.1 단순화된 구조
- 복잡한 메시지 큐 대신 직접 함수 호출
- 고급 추상화 패턴 제외
- 기본적인 에러 처리에 집중

### 9.2 필수 기능에 집중
- 핵심 유즈케이스 8개 구현
- 안정성보다 기능 구현 우선
- 최소한의 테스트 코드 (시나리오 테스트만)

### 9.3 확장성 고려사항
- 프로덕션 단계에서 확장 가능한 구조 유지
- 모듈간 낮은 결합도 유지
- 데이터 모델 변경 가능성 고려
