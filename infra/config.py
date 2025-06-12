"""
IACSRAG 전역 설정 및 환경변수 관리

Pydantic Settings를 사용한 타입 안전한 설정 관리
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 전역 설정"""
    
    # 애플리케이션 기본 설정
    app_name: str = Field(default="iacsrag", description="애플리케이션 이름")
    app_version: str = Field(default="0.1.0", description="애플리케이션 버전")
    app_environment: str = Field(default="development", description="실행 환경")
    app_debug: bool = Field(default=True, description="디버그 모드")
    app_log_level: str = Field(default="DEBUG", description="로그 레벨")
    
    # API 설정
    api_host: str = Field(default="0.0.0.0", description="API 호스트")
    api_port: int = Field(default=8000, description="API 포트")
    api_reload: bool = Field(default=True, description="개발 모드 자동 재시작")
    
    # MongoDB 설정
    mongodb_url: str = Field(
        default="mongodb://admin:password@localhost:27017",
        description="MongoDB 연결 URL"
    )
    mongodb_database: str = Field(default="iacsrag_dev", description="MongoDB 데이터베이스명")
    mongodb_min_pool_size: int = Field(default=10, description="MongoDB 최소 연결 풀 크기")
    mongodb_max_pool_size: int = Field(default=100, description="MongoDB 최대 연결 풀 크기")
    
    # Qdrant 설정
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant 서버 URL")
    qdrant_collection_name: str = Field(default="documents", description="Qdrant 컬렉션명")
    qdrant_vector_size: int = Field(default=1536, description="벡터 차원 크기")
    qdrant_distance_metric: str = Field(default="Cosine", description="거리 측정 방식")
    
    # Redis 설정
    redis_url: str = Field(default="redis://localhost:6379", description="Redis 연결 URL")
    redis_db: int = Field(default=0, description="Redis 데이터베이스 번호")
    redis_password: Optional[str] = Field(default=None, description="Redis 비밀번호")
    redis_max_connections: int = Field(default=10, description="Redis 최대 연결 수")


    # OpenAI API 설정
    openai_api_key: str = Field(default="", description="OpenAI API 키")
    openai_model: str = Field(default="text-embedding-3-small", description="OpenAI 임베딩 모델")
    openai_max_tokens: int = Field(default=8191, description="OpenAI 최대 토큰 수")
    openai_temperature: float = Field(default=0.1, description="OpenAI 온도 설정")
    
    # 이메일 수집 설정
    email_batch_size: int = Field(default=50, description="이메일 배치 처리 크기")
    email_collection_interval: int = Field(default=300, description="이메일 수집 간격(초)")
    email_max_retries: int = Field(default=3, description="이메일 수집 최대 재시도 횟수")
    email_retry_delay: int = Field(default=60, description="이메일 수집 재시도 대기시간(초)")
    
    # 스레드 관리 설정
    thread_prefix_pattern: str = Field(
        default=r"^([A-Z]{2,4}\d{3,6})",
        description="스레드 프리픽스 정규식 패턴"
    )
    thread_auto_close_days: int = Field(default=30, description="스레드 자동 종료 기간(일)")
    thread_cleanup_interval: int = Field(default=3600, description="스레드 정리 간격(초)")
    
    # 참여자 관리 설정
    member_unknown_domain_handling: str = Field(
        default="flag",
        description="미등록 도메인 처리 방식"
    )
    member_role_cache_ttl: int = Field(default=3600, description="참여자 역할 캐시 TTL(초)")
    
    # 마감일 관리 설정
    deadline_default_days: int = Field(default=7, description="기본 마감일(일)")
    deadline_urgent_days: int = Field(default=3, description="긴급 마감일(일)")
    deadline_final_days: int = Field(default=14, description="최종 확인 마감일(일)")
    deadline_check_interval: int = Field(default=3600, description="마감일 체크 간격(초)")
    
    # 알림 설정
    notification_email_enabled: bool = Field(default=True, description="이메일 알림 활성화")
    notification_slack_enabled: bool = Field(default=False, description="슬랙 알림 활성화")
    notification_smtp_host: str = Field(default="localhost", description="SMTP 호스트")
    notification_smtp_port: int = Field(default=587, description="SMTP 포트")
    notification_smtp_user: Optional[str] = Field(default=None, description="SMTP 사용자명")
    notification_smtp_password: Optional[str] = Field(default=None, description="SMTP 비밀번호")
    notification_from_email: str = Field(
        default="noreply@iacsrag.org",
        description="발신 이메일 주소"
    )
    
    # Slack 설정
    slack_bot_token: Optional[str] = Field(default=None, description="Slack 봇 토큰")
    slack_signing_secret: Optional[str] = Field(default=None, description="Slack 서명 시크릿")
    slack_default_channel: str = Field(default="#general", description="Slack 기본 채널")
    
    # 완료 판정 설정
    completion_final_keywords: str = Field(
        default="Final,Closed,Complete,Resolved",
        description="완료 키워드 목록"
    )
    completion_check_interval: int = Field(default=1800, description="완료 체크 간격(초)")
    completion_sentiment_threshold: float = Field(
        default=0.8,
        description="완료 감정 분석 임계값"
    )
    
    # 이슈 분석 설정
    issue_extraction_enabled: bool = Field(default=True, description="이슈 추출 활성화")
    issue_similarity_threshold: float = Field(default=0.85, description="이슈 유사도 임계값")
    issue_tag_categories: str = Field(
        default="RISK,OBJECTION,AGREEMENT,QUESTION,REQUIREMENT",
        description="이슈 태그 카테고리"
    )
    
    # 검색 설정
    search_default_limit: int = Field(default=20, description="검색 기본 제한 수")
    search_max_limit: int = Field(default=100, description="검색 최대 제한 수")
    search_similarity_threshold: float = Field(default=0.7, description="검색 유사도 임계값")
    search_hybrid_weight: float = Field(default=0.5, description="하이브리드 검색 가중치")
    
    # 대시보드 설정
    dashboard_refresh_interval: int = Field(default=30, description="대시보드 새로고침 간격(초)")
    dashboard_data_retention_days: int = Field(default=90, description="대시보드 데이터 보존 기간(일)")
    dashboard_export_max_records: int = Field(
        default=10000,
        description="대시보드 내보내기 최대 레코드 수"
    )
    
    # 린트 검사 설정
    lint_enabled: bool = Field(default=True, description="린트 검사 활성화")
    lint_auto_correction: bool = Field(default=False, description="자동 정정 활성화")
    lint_notification_enabled: bool = Field(default=True, description="린트 알림 활성화")
    lint_rules_config_path: str = Field(
        default="./config/lint_rules.json",
        description="린트 규칙 설정 파일 경로"
    )
    
    # 성능 설정
    max_concurrent_tasks: int = Field(default=10, description="최대 동시 작업 수")
    rate_limit_per_minute: int = Field(default=1000, description="분당 요청 제한")
    connection_timeout: int = Field(default=30, description="연결 타임아웃(초)")
    read_timeout: int = Field(default=60, description="읽기 타임아웃(초)")
    
    # 로깅 설정
    log_format: str = Field(default="json", description="로그 형식")
    log_file_path: str = Field(default="./logs/iacsrag.log", description="로그 파일 경로")
    log_file_max_size: str = Field(default="10MB", description="로그 파일 최대 크기")
    log_file_backup_count: int = Field(default=5, description="로그 파일 백업 개수")
    log_console_enabled: bool = Field(default=True, description="콘솔 로그 활성화")
    
    # 보안 설정
    secret_key: str = Field(
        default="your_secret_key_here_change_in_production",
        description="시크릿 키"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 알고리즘")
    jwt_expire_minutes: int = Field(default=1440, description="JWT 만료 시간(분)")
    allowed_hosts: str = Field(default="localhost,127.0.0.1", description="허용된 호스트 목록")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="CORS 허용 오리진"
    )
    
    # 개발 도구 설정
    enable_profiling: bool = Field(default=False, description="프로파일링 활성화")
    enable_debug_toolbar: bool = Field(default=False, description="디버그 툴바 활성화")
    mock_external_apis: bool = Field(default=False, description="외부 API 모킹 활성화")
    
    # 테스트 설정
    test_database_url: str = Field(
        default="mongodb://admin:password@localhost:27017/iacsrag_test",
        description="테스트 데이터베이스 URL"
    )
    test_qdrant_collection: str = Field(default="test_documents", description="테스트 Qdrant 컬렉션")
    test_skip_slow_tests: bool = Field(default=False, description="느린 테스트 건너뛰기")

    @validator("app_environment")
    def validate_environment(cls, v: str) -> str:
        """환경 설정 검증"""
        valid_environments = ["development", "testing", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_environments}")
        return v

    @validator("app_log_level")
    def validate_log_level(cls, v: str) -> str:
        """로그 레벨 검증"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    @validator("qdrant_distance_metric")
    def validate_distance_metric(cls, v: str) -> str:
        """Qdrant 거리 측정 방식 검증"""
        valid_metrics = ["Cosine", "Dot", "Euclid"]
        if v not in valid_metrics:
            raise ValueError(f"Invalid distance metric: {v}. Must be one of {valid_metrics}")
        return v

    @property
    def allowed_hosts_list(self) -> List[str]:
        """허용된 호스트를 리스트로 반환"""
        return [host.strip() for host in self.allowed_hosts.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS 오리진을 리스트로 반환"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def completion_final_keywords_list(self) -> List[str]:
        """완료 키워드를 리스트로 반환"""
        return [keyword.strip() for keyword in self.completion_final_keywords.split(",")]

    @property
    def issue_tag_categories_list(self) -> List[str]:
        """이슈 태그 카테고리를 리스트로 반환"""
        return [category.strip() for category in self.issue_tag_categories.split(",")]

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.app_environment == "production"

    @property
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.app_environment == "development"

    @property
    def is_testing(self) -> bool:
        """테스트 환경 여부"""
        return self.app_environment == "testing"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# 전역 설정 인스턴스
settings = Settings()


def get_settings() -> Settings:
    """설정 인스턴스 반환 (의존성 주입용)"""
    return settings
