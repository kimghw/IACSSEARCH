"""Search 임베딩 생성 서비스

OpenAI API를 사용하여 검색 질의를 벡터 임베딩으로 변환
캐시 관리 및 재시도 로직 포함
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

import structlog
from openai import APIError, RateLimitError, Timeout

from infra.vector_store import VectorStoreManager, get_vector_manager

from .schema import EmbeddingRequest
from .cache_manager import SearchCacheManager, get_search_cache_manager

logger = structlog.get_logger(__name__)


class SearchEmbeddingService:
    """임베딩 생성 전용 서비스"""
    
    def __init__(self):
        """SearchEmbeddingService 초기화 - 의존성 없이 생성"""
        self.vector_manager: Optional[VectorStoreManager] = None
        self.cache_manager: Optional[SearchCacheManager] = None
        self._initialized = False
        
        # 설정
        self.max_retries = 3
        self.retry_delay = 1.0  # 초
        self.timeout = 30.0  # 초
        self.cache_ttl = 3600  # 1시간
        
        # 통계
        self._cache_hits = 0
        self._cache_misses = 0
        self._api_calls = 0
        self._api_errors = 0
    
    async def set_dependencies(self, **kwargs) -> None:
        """Orchestrator에서 의존성 주입
        
        Args:
            cache_manager: 캐시 관리자 인스턴스
        """
        if 'cache_manager' in kwargs:
            self.cache_manager = kwargs['cache_manager']
            self._initialized = True
            logger.debug("SearchEmbeddingService 의존성 주입 완료")
    
    def _ensure_dependencies(self) -> None:
        """의존성 주입 확인"""
        if not self._initialized or not self.cache_manager:
            raise RuntimeError("SearchEmbeddingService: 의존성이 주입되지 않았습니다. set_dependencies()를 먼저 호출하세요.")
    
    # === 메인 처리 함수 ===
    
    async def search_embedding_create(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """텍스트를 임베딩으로 변환
        
        Args:
            text: 임베딩할 텍스트
            use_cache: 캐시 사용 여부
            
        Returns:
            임베딩 벡터
        """
        self._ensure_dependencies()
        
        # vector_manager는 직접 가져옴 (싱글톤)
        if not self.vector_manager:
            self.vector_manager = get_vector_manager()
        
        try:
            # 텍스트 정규화
            normalized_text = await self._search_embedding_normalize_text(text)
            
            # 캐시 조회
            if use_cache:
                cached_embedding = await self.cache_manager.cache_embedding_get(normalized_text)
                if cached_embedding:
                    self._cache_hits += 1
                    logger.debug(
                        "임베딩 캐시에서 반환",
                        text_preview=normalized_text[:50],
                        cache_hit_rate=self._get_cache_hit_rate()
                    )
                    return cached_embedding
            
            self._cache_misses += 1
            
            # OpenAI API 호출 (재시도 로직 포함)
            embedding = await self._create_embedding_with_retry(normalized_text)
            
            # 임베딩 검증
            is_valid = await self.search_embedding_validate(embedding)
            if not is_valid:
                raise ValueError("생성된 임베딩이 유효하지 않습니다")
            
            # 캐시 저장
            if use_cache:
                await self.cache_manager.cache_embedding_set(normalized_text, embedding)
            
            logger.info(
                "임베딩 생성 완료",
                text_length=len(text),
                embedding_dimension=len(embedding),
                cache_hit_rate=self._get_cache_hit_rate()
            )
            
            return embedding
            
        except Exception as e:
            logger.error(
                "임베딩 생성 실패",
                text_preview=text[:50],
                error=str(e),
                api_error_rate=self._get_api_error_rate()
            )
            raise
    
    
    # === 검증 및 최적화 ===
    
    async def search_embedding_validate(
        self,
        embedding: List[float]
    ) -> bool:
        """임베딩 유효성 검증
        
        Args:
            embedding: 검증할 임베딩
            
        Returns:
            유효성 여부
        """
        # 기본 검증
        if not embedding or not isinstance(embedding, list):
            return False
        
        # 차원 검증 (OpenAI ada-002는 1536차원)
        expected_dimension = 1536
        if len(embedding) != expected_dimension:
            logger.warning(
                "임베딩 차원 불일치",
                expected=expected_dimension,
                actual=len(embedding)
            )
            return False
        
        # 값 범위 검증
        if not all(isinstance(v, (int, float)) for v in embedding):
            return False
        
        # 제로 벡터 검증
        if all(v == 0 for v in embedding):
            logger.warning("제로 벡터 감지")
            return False
        
        # 정규화 검증 (L2 norm이 대략 1에 가까워야 함)
        norm = sum(v * v for v in embedding) ** 0.5
        if abs(norm - 1.0) > 0.1:  # 10% 오차 허용
            logger.debug("임베딩 정규화 필요", norm=norm)
        
        return True
    
    # === 내부 헬퍼 함수 ===
    
    async def _search_embedding_normalize_text(
        self,
        text: str
    ) -> str:
        """텍스트 정규화
        
        Args:
            text: 정규화할 텍스트
            
        Returns:
            정규화된 텍스트
        """
        # 공백 정규화
        normalized = ' '.join(text.split())
        
        # 최대 길이 제한 (토큰 제한 고려)
        max_length = 8000  # 대략 2000 토큰
        if len(normalized) > max_length:
            normalized = normalized[:max_length] + "..."
            logger.warning("텍스트 길이 초과로 잘림", original_length=len(text))
        
        return normalized.strip()
    
    
    async def _create_embedding_with_retry(
        self,
        text: str
    ) -> List[float]:
        """재시도 로직을 포함한 임베딩 생성
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            임베딩 벡터
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                self._api_calls += 1
                
                # 지수 백오프
                if attempt > 0:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.debug(f"재시도 대기 중... {delay}초")
                    await asyncio.sleep(delay)
                
                # OpenAI API 호출
                embedding = await self.vector_manager.create_embedding(text)
                
                logger.debug(
                    "OpenAI API 호출 성공",
                    attempt=attempt + 1,
                    text_length=len(text)
                )
                
                return embedding
                
            except RateLimitError as e:
                self._api_errors += 1
                last_error = e
                logger.warning(
                    "OpenAI API 속도 제한",
                    attempt=attempt + 1,
                    error=str(e)
                )
                # 속도 제한은 더 긴 대기
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5)
                    
            except Timeout as e:
                self._api_errors += 1
                last_error = e
                logger.warning(
                    "OpenAI API 타임아웃",
                    attempt=attempt + 1,
                    error=str(e)
                )
                
            except APIError as e:
                self._api_errors += 1
                last_error = e
                logger.error(
                    "OpenAI API 오류",
                    attempt=attempt + 1,
                    error=str(e)
                )
                # API 오류는 재시도하지 않음
                break
                
            except Exception as e:
                self._api_errors += 1
                last_error = e
                logger.error(
                    "예상치 못한 오류",
                    attempt=attempt + 1,
                    error=str(e)
                )
        
        # 모든 재시도 실패
        raise Exception(f"임베딩 생성 실패 (재시도 {self.max_retries}회): {last_error}")
    
    def _get_cache_hit_rate(self) -> float:
        """캐시 히트율 계산"""
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return 0.0
        return self._cache_hits / total
    
    def _get_api_error_rate(self) -> float:
        """API 오류율 계산"""
        if self._api_calls == 0:
            return 0.0
        return self._api_errors / self._api_calls
    
    async def get_stats(self) -> Dict[str, Any]:
        """서비스 통계 반환"""
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._get_cache_hit_rate(),
            "api_calls": self._api_calls,
            "api_errors": self._api_errors,
            "api_error_rate": self._get_api_error_rate(),
            "cache_ttl_seconds": self.cache_ttl
        }
