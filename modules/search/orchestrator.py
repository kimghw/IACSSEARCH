"""Search 오케스트레이터

전체 검색 프로세스를 조율하고 각 서비스를 연동하는 핵심 컴포넌트
오케스트레이터 패턴을 적용하여 호출 순서와 흐름을 관리
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog

from infra.cache import get_cache_service
from infra.database import get_database
from infra.vector_store import get_vector_manager, connect_to_qdrant, connect_to_openai

from .repository import SearchRepository
from .schema import (
    CollectionStrategy,
    HealthStatus,
    SearchFilters,
    SearchMode,
    SearchQuery,
    SearchResponse,
)
from .search_embedding_service import SearchEmbeddingService
from .search_query_processor import SearchQueryProcessor
from .search_result_enricher import SearchResultEnricher
from .search_vector_service import SearchVectorService
from .search_performance_monitor import SearchPerformanceMonitor
from .cache_manager import SearchCacheManager, get_search_cache_manager

logger = structlog.get_logger(__name__)


class SearchOrchestrator:
    """검색 프로세스 오케스트레이터
    
    레이지 싱글톤 패턴을 사용하여 공통 의존성을 관리하고
    각 서비스에 의존성을 주입하는 중앙 관리자 역할
    """
    
    # 클래스 레벨 싱글톤 인스턴스
    _repository_instance: Optional[SearchRepository] = None
    _cache_manager_instance: Optional[SearchCacheManager] = None
    
    def __init__(self):
        """SearchOrchestrator 초기화"""
        # 서비스 초기화는 지연 초기화로 처리
        self.query_processor: Optional[SearchQueryProcessor] = None
        self.embedding_service: Optional[SearchEmbeddingService] = None
        self.vector_service: Optional[SearchVectorService] = None
        self.result_enricher: Optional[SearchResultEnricher] = None
        self.repository: Optional[SearchRepository] = None
        self.performance_monitor: Optional[SearchPerformanceMonitor] = None
        
        self._initialized = False
        
        # 통계 추적
        self._total_searches = 0
        self._total_errors = 0
        self._average_response_time = 0.0
    
    async def _ensure_initialized(self) -> None:
        """서비스 초기화 확인"""
        if not self._initialized:
            # 1. 공통 의존성 초기화
            await self._init_shared_dependencies()
            
            # 2. 각 서비스 초기화 (의존성 없이)
            self.query_processor = SearchQueryProcessor()
            self.embedding_service = SearchEmbeddingService()
            self.vector_service = SearchVectorService()
            self.result_enricher = SearchResultEnricher()
            self.repository = SearchOrchestrator._repository_instance  # 싱글톤 사용
            self.performance_monitor = SearchPerformanceMonitor()
            
            # 3. 각 서비스에 의존성 주입
            await self._inject_dependencies()
            
            self._initialized = True
            logger.info("SearchOrchestrator 초기화 완료")
    
    async def _init_shared_dependencies(self) -> None:
        """공통 의존성 레이지 싱글톤 초기화"""
        # 1. 외부 서비스 연결 확인 및 초기화
        await self._ensure_external_services()
        
        # 2. Repository 싱글톤 초기화
        if SearchOrchestrator._repository_instance is None:
            SearchOrchestrator._repository_instance = SearchRepository()
            await SearchOrchestrator._repository_instance._ensure_initialized()
            logger.debug("SearchRepository 싱글톤 인스턴스 생성")
        
        # 3. CacheManager 싱글톤 초기화
        if SearchOrchestrator._cache_manager_instance is None:
            SearchOrchestrator._cache_manager_instance = await get_search_cache_manager()
            logger.debug("SearchCacheManager 싱글톤 인스턴스 생성")
    
    async def _ensure_external_services(self) -> None:
        """외부 서비스 연결 확인 및 초기화"""
        try:
            # MongoDB 연결 확인 및 초기화
            from infra.database import connect_to_mongodb, get_database
            try:
                get_database()
                logger.debug("MongoDB 이미 연결됨")
            except RuntimeError:
                logger.info("MongoDB 연결 초기화 중...")
                await connect_to_mongodb()
                logger.info("MongoDB 연결 완료")
            
            # OpenAI 연결 확인 및 초기화  
            from infra.config import get_settings
            from infra.vector_store import get_openai_client
            settings = get_settings()
            if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
                try:
                    # OpenAI 클라이언트가 이미 초기화되어 있는지 확인
                    try:
                        get_openai_client()
                        logger.debug("OpenAI 클라이언트 이미 초기화됨")
                    except RuntimeError:
                        logger.info("OpenAI 클라이언트 초기화 중...")
                        await connect_to_openai()
                        logger.info("OpenAI 클라이언트 초기화 완료")
                except Exception as e:
                    logger.warning(f"OpenAI 클라이언트 초기화 실패: {e}")
            else:
                logger.warning("OpenAI API 키가 설정되지 않음")
            
            # Qdrant 연결 확인 및 초기화
            from infra.vector_store import get_qdrant_client
            try:
                get_qdrant_client()
                logger.debug("Qdrant 이미 연결됨")
            except RuntimeError:
                logger.info("Qdrant 연결 초기화 중...")
                await connect_to_qdrant()
                logger.info("Qdrant 연결 완료")
                
        except Exception as e:
            logger.warning(f"외부 서비스 초기화 중 일부 실패: {e}")
            # 테스트 환경에서는 계속 진행
    
    async def _inject_dependencies(self) -> None:
        """각 서비스에 의존성 주입"""
        repo = SearchOrchestrator._repository_instance
        cache = SearchOrchestrator._cache_manager_instance
        
        # 각 서비스에 필요한 의존성만 주입
        await self.query_processor.set_dependencies(cache_manager=cache)
        await self.embedding_service.set_dependencies(cache_manager=cache)
        await self.vector_service.set_dependencies(repository=repo, cache_manager=cache)
        await self.result_enricher.set_dependencies(repository=repo)
        await self.performance_monitor.set_dependencies(cache_manager=cache)
        
        logger.debug("모든 서비스에 의존성 주입 완료")
    
    # === 메인 오케스트레이션 함수 ===
    
    async def search_orchestrator_process(
        self,
        query: SearchQuery
    ) -> SearchResponse:
        """검색 프로세스 전체 조율
        
        Args:
            query: 검색 질의 정보
            
        Returns:
            검색 응답
        """
        await self._ensure_initialized()
        
        start_time = time.time()
        query_id = str(uuid4())
        
        try:
            logger.info(
                "검색 프로세스 시작",
                query_id=query_id,
                query_text=query.query_text[:50],
                mode=query.search_mode.value
            )
            
            # 1. 요청 검증
            await self._search_orchestrator_validate_request(query.query_text)
            
            # 2. 질의 처리 (필터 추출 등)
            processed_query = None
            if query.search_mode != SearchMode.VECTOR_ONLY or query.auto_extract_filters:
                processed_query = await self.query_processor.search_query_process(
                    query_text=query.query_text,
                    filters=query.filters
                )
                # 추출된 필터 적용
                if processed_query.extracted_filters:
                    query.filters = processed_query.extracted_filters
            
            # 3. 임베딩 생성 (벡터 검색이 필요한 경우에만)
            embedding = None
            if query.search_mode in [SearchMode.HYBRID, SearchMode.VECTOR_ONLY]:
                embedding = await self.embedding_service.search_embedding_create(
                    text=processed_query.normalized_text if processed_query else query.query_text
                )
            
            # 4. 벡터 검색
            vector_matches = await self.vector_service.search_vector_find(
                embedding=embedding,
                query=query
            )
            
            if not vector_matches:
                logger.info("검색 결과 없음", query_id=query_id)
                return self._create_empty_response(query, query_id, start_time)
            
            # 5. 결과 보강
            enriched_results = await self.result_enricher.search_result_enrich(
                vector_matches=vector_matches,
                query_text=query.query_text
            )
            
            # 6. 응답 생성
            search_time = self._search_orchestrator_measure_time(start_time)
            
            # 7. 검색 로그 기록
            await self._search_orchestrator_log_search(
                query=query.query_text,
                results=enriched_results,
                search_time=search_time,
                query_id=query_id,
                mode=query.search_mode
            )
            
            # 통계 업데이트
            self._update_statistics(search_time, success=True)
            
            # 응답 생성
            response = SearchResponse(
                query=query.query_text,
                results=enriched_results,
                total_count=len(enriched_results),
                returned_count=len(enriched_results),
                search_time_ms=search_time,
                query_id=query_id,
                search_mode=query.search_mode,
                collections_searched=self._get_searched_collections(query),
                filters_applied=bool(query.filters),
                cache_hit=False,  # 추후 캐시 히트 추적 구현
                search_metadata={
                    "embedding_model": "text-embedding-ada-002",
                    "vector_dimensions": 1536,
                    "score_threshold": query.score_threshold,
                    "processed_query": processed_query.normalized_text if processed_query else None
                }
            )
            
            logger.info(
                "검색 프로세스 완료",
                query_id=query_id,
                result_count=len(enriched_results),
                search_time_ms=search_time
            )
            
            return response
            
        except Exception as e:
            self._update_statistics(time.time() - start_time, success=False)
            logger.error(
                "검색 프로세스 실패",
                query_id=query_id,
                error=str(e),
                query_text=query.query_text[:50]
            )
            raise
    
    # === 헬스체크 ===
    
    async def search_orchestrator_health_check(self) -> HealthStatus:
        """서비스 헬스체크
        
        Returns:
            헬스 상태 정보
        """
        await self._ensure_initialized()
        
        health_checks = {
            "database": False,
            "cache": False,
            "vector_store": False,
            "openai": False
        }
        
        try:
            # Database 체크
            db = get_database()
            if db:
                health_checks["database"] = True
        except:
            pass
        
        try:
            # Cache 체크
            cache = await get_cache_service()
            if cache:
                await cache.cache_get("health_check")
                health_checks["cache"] = True
        except:
            pass
        
        try:
            # Vector Store 체크
            vector_manager = get_vector_manager()
            if vector_manager:
                health_checks["vector_store"] = True
        except:
            pass
        
        try:
            # OpenAI 체크 (임베딩 서비스 통계로 확인)
            stats = await self.embedding_service.get_stats()
            if stats.get("api_calls", 0) > 0 or stats.get("cache_hits", 0) > 0:
                health_checks["openai"] = True
        except:
            pass
        
        # 전체 상태 계산
        all_healthy = all(health_checks.values())
        status = "healthy" if all_healthy else "degraded"
        
        return HealthStatus(
            status=status,
            service="search",
            checks=health_checks,
            stats={
                "total_searches": self._total_searches,
                "total_errors": self._total_errors,
                "average_response_time_ms": round(self._average_response_time, 2),
                "uptime_seconds": 0  # 추후 구현
            },
            timestamp=datetime.now()
        )
    
    # === 내부 조율 함수 ===
    
    async def _search_orchestrator_validate_request(
        self,
        query_text: str
    ) -> None:
        """요청 유효성 검증
        
        Args:
            query_text: 검증할 질의
            
        Raises:
            ValueError: 유효하지 않은 요청
        """
        if not query_text or not query_text.strip():
            raise ValueError("검색어가 비어있습니다")
        
        if len(query_text) > 1000:
            raise ValueError("검색어가 너무 깁니다 (최대 1000자)")
        
        if len(query_text.strip()) < 2:
            raise ValueError("검색어가 너무 짧습니다 (최소 2자)")
    
    def _search_orchestrator_measure_time(
        self,
        start_time: float
    ) -> int:
        """검색 소요 시간 측정
        
        Args:
            start_time: 시작 시간
            
        Returns:
            소요 시간 (밀리초)
        """
        elapsed = time.time() - start_time
        return int(elapsed * 1000)
    
    async def _search_orchestrator_log_search(
        self,
        query: str,
        results: List[Any],
        search_time: int,
        query_id: str,
        mode: SearchMode
    ) -> None:
        """검색 로그 기록
        
        Args:
            query: 검색 질의
            results: 검색 결과
            search_time: 소요 시간
            query_id: 검색 ID
            mode: 검색 모드
        """
        try:
            await self.repository.search_repo_log_query(
                query_text=query,
                results=results,
                search_mode=mode.value,
                search_time_ms=search_time,
                user_id=None,
                error_message=None
            )
        except Exception as e:
            logger.warning("검색 로그 기록 실패", error=str(e))
    
    def _get_searched_collections(self, query: SearchQuery) -> List[str]:
        """검색된 컬렉션 목록 반환"""
        if query.target_collections:
            return query.target_collections
        
        if query.collection_strategy == CollectionStrategy.SINGLE:
            return ["emails"]
        elif query.collection_strategy == CollectionStrategy.AUTO:
            return ["emails", "documents", "messages"]
        else:
            return ["emails"]
    
    def _create_empty_response(
        self,
        query: SearchQuery,
        query_id: str,
        start_time: float
    ) -> SearchResponse:
        """빈 검색 응답 생성"""
        search_time = self._search_orchestrator_measure_time(start_time)
        
        return SearchResponse(
            query=query.query_text,
            results=[],
            total_count=0,
            returned_count=0,
            search_time_ms=search_time,
            query_id=query_id,
            search_mode=query.search_mode,
            collections_searched=self._get_searched_collections(query),
            filters_applied=bool(query.filters),
            cache_hit=False,
            search_metadata={
                "message": "검색 결과가 없습니다"
            }
        )
    
    def _update_statistics(self, response_time_ms: float, success: bool) -> None:
        """통계 업데이트"""
        self._total_searches += 1
        
        if not success:
            self._total_errors += 1
        
        # 이동 평균 계산
        if self._average_response_time == 0:
            self._average_response_time = response_time_ms
        else:
            # 지수 이동 평균 (EMA)
            alpha = 0.1  # 평활 계수
            self._average_response_time = (
                alpha * response_time_ms + 
                (1 - alpha) * self._average_response_time
            )
    
    # === 성능 모니터링 메서드 ===
    
    async def search_orchestrator_get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭스 조회
        
        Returns:
            성능 메트릭스 요약
        """
        await self._ensure_initialized()
        
        return await self.performance_monitor.search_monitor_get_metrics_summary()
    
    async def search_orchestrator_get_optimization_suggestions(self) -> Dict[str, Any]:
        """성능 최적화 제안 조회
        
        Returns:
            최적화 제안 사항
        """
        await self._ensure_initialized()
        
        suggestions = await self.performance_monitor.search_monitor_optimize_cache_strategy()
        bottlenecks = await self.performance_monitor.search_monitor_identify_bottlenecks()
        
        return {
            "cache_optimization": suggestions,
            "bottlenecks": bottlenecks,
            "recommendations_summary": self._generate_recommendations_summary(
                suggestions, bottlenecks
            )
        }
    
    def _generate_recommendations_summary(
        self, 
        cache_suggestions: Dict[str, Any], 
        bottlenecks: List[Dict[str, Any]]
    ) -> str:
        """최적화 권장사항 요약 생성"""
        summary = []
        
        # 캐시 최적화 제안
        if cache_suggestions["overall_health"] == "needs_improvement":
            summary.append("캐시 전략 개선이 필요합니다.")
            
        # 병목 지점 요약
        if bottlenecks:
            high_severity = [b for b in bottlenecks if b["severity"] == "high"]
            if high_severity:
                summary.append(f"{len(high_severity)}개의 심각한 병목 지점이 발견되었습니다.")
        
        # 전체 성능 평가
        if self._average_response_time > 1000:
            summary.append("평균 응답 시간이 목표치를 초과하고 있습니다.")
        
        return " ".join(summary) if summary else "성능이 양호합니다."
