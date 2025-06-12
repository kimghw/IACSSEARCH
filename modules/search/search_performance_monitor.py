"""검색 모듈 성능 모니터링 유틸리티"""
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from collections import defaultdict

from infra.cache import get_cache_service
from infra.database import get_database_manager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """성능 측정 지표"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # 응답 시간 (밀리초)
    response_times: List[float] = field(default_factory=list)
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # 캐시 성능
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    
    # 컴포넌트별 시간
    query_processing_time: float = 0.0
    embedding_generation_time: float = 0.0
    vector_search_time: float = 0.0
    result_enrichment_time: float = 0.0
    
    # 메모리 사용량 (MB)
    peak_memory_usage: float = 0.0
    avg_memory_usage: float = 0.0


class SearchPerformanceMonitor:
    """검색 성능 모니터링 클래스"""
    
    def __init__(self):
        self.cache = get_cache_service()
        self.db = get_database_manager()
        self.metrics = PerformanceMetrics()
        self.component_timings: Dict[str, List[float]] = defaultdict(list)
        
    async def search_monitor_start_request(self) -> Dict[str, Any]:
        """요청 시작 시점 기록"""
        return {
            "start_time": time.time(),
            "request_id": f"req_{int(time.time() * 1000)}",
            "component_times": {}
        }
    
    async def search_monitor_component_time(
        self, 
        request_context: Dict[str, Any], 
        component: str, 
        elapsed_time: float
    ) -> None:
        """컴포넌트별 실행 시간 기록"""
        request_context["component_times"][component] = elapsed_time
        self.component_timings[component].append(elapsed_time)
        
    async def search_monitor_cache_access(self, hit: bool) -> None:
        """캐시 접근 기록"""
        if hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
            
    async def search_monitor_complete_request(
        self, 
        request_context: Dict[str, Any], 
        success: bool = True
    ) -> None:
        """요청 완료 및 메트릭스 업데이트"""
        end_time = time.time()
        response_time = (end_time - request_context["start_time"]) * 1000  # ms
        
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
            
        self.metrics.response_times.append(response_time)
        
        # 컴포넌트별 평균 시간 계산
        for component, times in self.component_timings.items():
            if times:
                avg_time = sum(times) / len(times)
                setattr(self.metrics, f"{component}_time", avg_time)
        
        # 캐시 히트율 계산
        total_cache_accesses = self.metrics.cache_hits + self.metrics.cache_misses
        if total_cache_accesses > 0:
            self.metrics.cache_hit_rate = (
                self.metrics.cache_hits / total_cache_accesses * 100
            )
            
        # 통계 저장
        await self._save_metrics_to_db(request_context, response_time)
        
    async def search_monitor_calculate_percentiles(self) -> Dict[str, float]:
        """응답 시간 백분위수 계산"""
        if not self.metrics.response_times:
            return {"p50": 0, "p95": 0, "p99": 0}
            
        sorted_times = sorted(self.metrics.response_times)
        n = len(sorted_times)
        
        p50_idx = int(n * 0.5)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        return {
            "p50": sorted_times[p50_idx] if p50_idx < n else sorted_times[-1],
            "p95": sorted_times[p95_idx] if p95_idx < n else sorted_times[-1],
            "p99": sorted_times[p99_idx] if p99_idx < n else sorted_times[-1]
        }
        
    async def search_monitor_get_metrics_summary(self) -> Dict[str, Any]:
        """메트릭스 요약 반환"""
        percentiles = await self.search_monitor_calculate_percentiles()
        
        return {
            "total_requests": self.metrics.total_requests,
            "success_rate": (
                self.metrics.successful_requests / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0 else 0
            ),
            "cache_hit_rate": self.metrics.cache_hit_rate,
            "response_times": {
                "avg": (
                    sum(self.metrics.response_times) / len(self.metrics.response_times)
                    if self.metrics.response_times else 0
                ),
                "p50": percentiles["p50"],
                "p95": percentiles["p95"],
                "p99": percentiles["p99"]
            },
            "component_times": {
                "query_processing": self.metrics.query_processing_time,
                "embedding_generation": self.metrics.embedding_generation_time,
                "vector_search": self.metrics.vector_search_time,
                "result_enrichment": self.metrics.result_enrichment_time
            }
        }
        
    async def search_monitor_optimize_cache_strategy(self) -> Dict[str, Any]:
        """캐시 전략 최적화 제안"""
        recommendations = []
        
        # 캐시 히트율이 낮은 경우
        if self.metrics.cache_hit_rate < 80:
            recommendations.append({
                "type": "cache_ttl",
                "message": "캐시 TTL을 늘려 히트율을 개선하세요",
                "current_hit_rate": self.metrics.cache_hit_rate,
                "target_hit_rate": 80
            })
            
        # 임베딩 생성 시간이 긴 경우
        if self.metrics.embedding_generation_time > 500:
            recommendations.append({
                "type": "embedding_cache",
                "message": "임베딩 캐시를 더 적극적으로 활용하세요",
                "current_time": self.metrics.embedding_generation_time,
                "target_time": 100
            })
            
        # 벡터 검색 시간이 긴 경우
        if self.metrics.vector_search_time > 300:
            recommendations.append({
                "type": "vector_index",
                "message": "Qdrant 인덱스 최적화가 필요합니다",
                "current_time": self.metrics.vector_search_time,
                "suggestions": [
                    "HNSW 파라미터 조정",
                    "결과 개수 제한",
                    "필터 조건 최적화"
                ]
            })
            
        return {
            "recommendations": recommendations,
            "overall_health": "good" if len(recommendations) == 0 else "needs_improvement"
        }
        
    async def search_monitor_identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """병목 지점 식별"""
        bottlenecks = []
        
        # 컴포넌트별 시간 분석
        total_time = sum([
            self.metrics.query_processing_time,
            self.metrics.embedding_generation_time,
            self.metrics.vector_search_time,
            self.metrics.result_enrichment_time
        ])
        
        if total_time > 0:
            components = [
                ("query_processing", self.metrics.query_processing_time),
                ("embedding_generation", self.metrics.embedding_generation_time),
                ("vector_search", self.metrics.vector_search_time),
                ("result_enrichment", self.metrics.result_enrichment_time)
            ]
            
            for component, time in components:
                percentage = (time / total_time) * 100
                if percentage > 40:  # 40% 이상 차지하면 병목
                    bottlenecks.append({
                        "component": component,
                        "time_ms": time,
                        "percentage": percentage,
                        "severity": "high" if percentage > 60 else "medium"
                    })
                    
        return bottlenecks
        
    async def _save_metrics_to_db(
        self, 
        request_context: Dict[str, Any], 
        response_time: float
    ) -> None:
        """메트릭스를 DB에 저장"""
        try:
            await self.db.execute_query(
                """
                INSERT INTO search_performance_logs 
                (request_id, timestamp, response_time_ms, component_times, 
                 cache_hit, success)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                request_context["request_id"],
                datetime.utcnow(),
                response_time,
                request_context["component_times"],
                request_context.get("cache_hit", False),
                request_context.get("success", True)
            )
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            
    async def search_monitor_cleanup_old_metrics(self, days: int = 7) -> None:
        """오래된 메트릭스 정리"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            await self.db.execute_query(
                """
                DELETE FROM search_performance_logs 
                WHERE timestamp < $1
                """,
                cutoff_date
            )
            logger.info(f"Cleaned up metrics older than {days} days")
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")


# 성능 모니터링 데코레이터
def monitor_performance(component_name: str):
    """성능 모니터링 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed_time = (time.time() - start_time) * 1000
                
                # 모니터링 컨텍스트가 있으면 기록
                if "monitoring_context" in kwargs:
                    monitor = SearchPerformanceMonitor()
                    await monitor.search_monitor_component_time(
                        kwargs["monitoring_context"],
                        component_name,
                        elapsed_time
                    )
                    
                return result
            except Exception as e:
                logger.error(f"Error in {component_name}: {e}")
                raise
                
        return wrapper
    return decorator
