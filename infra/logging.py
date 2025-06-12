"""
IACSRAG 로깅 설정 및 초기화

구조화된 로깅 시스템 설정
infra/core 아키텍쳐 지침: 연결, 초기화, 설정만 담당
"""

import sys
import logging
from pathlib import Path
import structlog
from structlog.processors import JSONRenderer
from structlog.stdlib import LoggingFactory
import colorama
from colorama import Fore, Style

from .config import settings

# 컬러 초기화
colorama.init(autoreset=True)


def setup_logging() -> None:
    """로깅 시스템을 초기화합니다."""
    
    # 로그 디렉토리 생성
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 로깅 레벨 설정
    log_level = getattr(logging, settings.app_log_level)
    
    # 기본 로깅 설정
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=_get_handlers()
    )
    
    # Structlog 설정
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            _get_renderer(),
        ],
        context_class=dict,
        logger_factory=LoggingFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 외부 라이브러리 로그 레벨 조정
    _configure_external_loggers()
    
    logger = get_logger(__name__)
    logger.info(
        "로깅 시스템이 초기화되었습니다",
        log_level=settings.app_log_level,
        log_format=settings.log_format,
        log_file=settings.log_file_path,
        console_enabled=settings.log_console_enabled
    )


def _get_handlers() -> list:
    """로깅 핸들러를 생성합니다."""
    handlers = []
    
    # 파일 핸들러
    if settings.log_file_path:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            filename=settings.log_file_path,
            maxBytes=_parse_size(settings.log_file_max_size),
            backupCount=settings.log_file_backup_count,
            encoding='utf-8'
        )
        handlers.append(file_handler)
    
    # 콘솔 핸들러
    if settings.log_console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)
    
    return handlers


def _get_renderer():
    """로그 렌더러를 반환합니다."""
    if settings.log_format == "json":
        return JSONRenderer()
    else:
        # 개발 환경용 컬러 렌더러
        return ColoredConsoleRenderer()


def _parse_size(size_str: str) -> int:
    """크기 문자열을 바이트로 변환합니다."""
    size_str = size_str.upper()
    if size_str.endswith("KB"):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith("MB"):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith("GB"):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)


def _configure_external_loggers() -> None:
    """외부 라이브러리의 로거 레벨을 조정합니다."""
    external_loggers = {
        "motor": "WARNING",
        "pymongo": "WARNING", 
        "qdrant_client": "WARNING",
        "httpx": "WARNING",
        "fastapi": "INFO",
        "uvicorn": "INFO",
        "openai": "WARNING",
        "azure": "WARNING",
        "msal": "WARNING"
    }
    
    for logger_name, level in external_loggers.items():
        logging.getLogger(logger_name).setLevel(getattr(logging, level))


class ColoredConsoleRenderer:
    """개발 환경용 컬러 콘솔 렌더러"""
    
    LEVEL_COLORS = {
        "debug": Fore.CYAN,
        "info": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "critical": Fore.MAGENTA + Style.BRIGHT,
    }
    
    def __call__(self, logger, method_name, event_dict):
        """로그를 컬러로 렌더링합니다."""
        level = event_dict.get("level", "info").lower()
        color = self.LEVEL_COLORS.get(level, "")
        
        # 기본 메시지 구성
        timestamp = event_dict.get("timestamp", "")
        logger_name = event_dict.get("logger", "")
        message = event_dict.get("event", "")
        
        # 추가 컨텍스트 정보
        context = {k: v for k, v in event_dict.items() 
                  if k not in ("timestamp", "logger", "level", "event")}
        
        # 포맷팅
        parts = []
        if timestamp:
            parts.append(f"{Fore.BLUE}{timestamp[:19]}{Style.RESET_ALL}")
        if logger_name:
            parts.append(f"{Fore.MAGENTA}{logger_name}{Style.RESET_ALL}")
        
        level_str = f"{color}[{level.upper()}]{Style.RESET_ALL}"
        parts.append(level_str)
        
        if message:
            parts.append(f"{color}{message}{Style.RESET_ALL}")
        
        result = " | ".join(parts)
        
        # 컨텍스트 정보 추가
        if context:
            context_str = " ".join([f"{k}={v}" for k, v in context.items()])
            result += f" {Fore.WHITE}{context_str}{Style.RESET_ALL}"
        
        return result


def get_logger(name: str) -> structlog.BoundLogger:
    """구조화된 로거를 반환합니다."""
    return structlog.get_logger(name)
