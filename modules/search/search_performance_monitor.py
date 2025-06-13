"""Search 성능 모니터링 서비스

검색 성능 메트릭 수집 및 분석
병목 지점 식별 및 최적화 제안
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

import structlog

from .cache_manager import SearchCacheManager, get_search_cache_manager

logger = structlog.get_logger(__name__)


class SearchPerformanceMonitor:
    """검색 성능 모니터링 서비스"""
    
    def __init__(self):
        """SearchPerformanceMonitor 초기화 - 의존성 없이 생성"""
        self.cache_manager: Optional[SearchCacheManager] = None
        self._initialized = False
        
        # 메트릭 추적
        self.metrics = defaultdict(list)
        self.operation_times = defaultdict(list)
        
    async def set_dependencies(self, **kwargs) -> None:
        """Orchestrator에서 의존성 주입
        
        Args:
            cache_manager: 캐시 관리자 인스턴스
        """
        if 'cache_manager' in kwargs:
            self.cache_manager = kwargs['cache_manager']
            self._initialized = True
            logger.debug("SearchPerformanceMonitor 의존성 주입 완료")
    
    def _ensure_dependencies(self) -> None:
        """의존성 주입 확인"""
        if not self._initialized or not self.cache_manager:
            raise RuntimeError("SearchPerformanceMonitor: 의존성이 주입되지 않았습니다. set_dependencies()를 먼저 호출하세요.")
    
    # === 메트릭 수집 ===
    
    async def search_monitor_record_operation(
        self,
        operation_name: str,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """작업 성능 기록
        
        Args:
            operation_name: 작업 이름
            duration_ms: 소요 시간 (밀리초)
            metadata: 추가 메타데이터
        """
        self._ensure_dependencies()
        
        record = {
            "operation": operation_name,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        
        # 메모리에 저장
        self.operation_times[operation_name].append(duration_ms)
        
        # 최근 1000개만 유지
        if len(self.operation_times[operation_name]) > 1000:
            self.operation_times[operation_name] = self.operation_times[operation_name][-1000:]
        
        # 캐시에도 저장 (집계용)
        await self.cache_manager.cache_performance_metric(operation_name, record)
    
    # === 메트릭 분석 ===
    
    async def search_monitor_get_metrics_summary(self) -> Dict[str, Any]:
        """성능 메트릭 요약 조회
        
        Returns:
            메트릭 요약 정보
        """
        self._ensure_dependencies()
        
        summary = {
            "operations": {},
            "total_operations": 0,
            "average_response_time": 0,
            "p95_response_time": 0,
            "p99_response_time": 0,
            "slowest_operations": [],
            "timestamp": datetime.now()
        }
        
        total_times = []
        
        for op_name, times in self.operation_times.items():
            if times:
                sorted_times = sorted(times)
                op_summary = {
                    "count": len(times),
                    "average_ms": sum(times) / len(times),
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "p50_ms": self._calculate_percentile(sorted_times, 50),
                    "p95_ms": self._calculate_percentile(sorted_times, 95),
                    "p99_ms": self._calculate_percentile(sorted_times, 99)
                }
                summary["operations"][op_name] = op_summary
                total_times.extend(times)
                
                # 가장 느린 작업 추적
                if op_summary["average_ms"] > 100:  # 100ms 이상
                    summary["slowest_operations"].append({
                        "operation": op_name,
                        "average_ms": op_summary["average_ms"],
                        "count": op_summary["count"]
                    })
        
        # 전체 통계
        if total_times:
            sorted_total = sorted(total_times)
            summary["total_operations"] = len(total_times)
            summary["average_response_time"] = sum(total_times) / len(total_times)
            summary["p95_response_time"] = self._calculate_percentile(sorted_total, 95)
            summary["p99_response_time"] = self._calculate_percentile(sorted_total, 99)
        
        # 가장 느린 작업 정렬
        summary["slowest_operations"].sort(key=lambda x: x["average_ms"], reverse=True)
        summary["slowest_operations"] = summary["slowest_operations"][:5]  # 상위 5개만
        
        return summary
    
    async def search_monitor_identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """병목 지점 식별
        
        Returns:
            병목 지점 목록
        """
        self._ensure_dependencies()
        
        bottlenecks = []
        
        # 각 작업별 분석
        for op_name, times in self.operation_times.items():
            if not times:
                continue
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            # 병목 판단 기준
            severity = None
            reason = None
            
            if avg_time > 500:  # 평균 500ms 이상
                severity = "high"
                reason = f"평균 응답 시간이 {avg_time:.0f}ms로 매우 느림"
            elif avg_time > 200:  # 평균 200ms 이상
                severity = "medium"
                reason = f"평균 응답 시간이 {avg_time:.0f}ms로 느림"
            elif max_time > 1000 and max_time > avg_time * 3:  # 스파이크
                severity = "low"
                reason = f"간헐적 지연 발생 (최대 {max_time:.0f}ms)"
            
            if severity:
                bottlenecks.append({
                    "operation": op_name,
                    "severity": severity,
                    "reason": reason,
                    "metrics": {
                        "average_ms": avg_time,
                        "max_ms": max_time,
                        "sample_count": len(times)
                    },
                    "recommendations": self._get_recommendations(op_name, avg_time)
                })
        
        # 심각도 순으로 정렬
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(key=lambda x: severity_order[x["severity"]])
        
        return bottlenecks
    
    async def search_monitor_optimize_cache_strategy(self) -> Dict[str, Any]:
        """캐시 전략 최적화 제안
        
        Returns:
            캐시 최적화 제안
        """
        self._ensure_dependencies()
        
        # 캐시 관련 메트릭 수집
        cache_metrics = {
            "embedding_cache": self._analyze_cache_performance("search_embedding_create"),
            "query_cache": self._analyze_cache_performance("search_query_process"),
            "result_cache": self._analyze_cache_performance("search_result_enrich")
        }
        
        suggestions = {
            "cache_improvements": [],
            "ttl_adjustments": [],
            "overall_health": "healthy"
        }
        
        # 각 캐시별 분석
        for cache_type, metrics in cache_metrics.items():
            if metrics:
                hit_rate = metrics.get("hit_rate", 0)
                avg_time = metrics.get("average_time", 0)
                
                if hit_rate < 0.7:  # 70% 미만
                    suggestions["cache_improvements"].append({
                        "cache": cache_type,
                        "issue": f"낮은 캐시 적중률 ({hit_rate:.1%})",
                        "action": "TTL 증가 또는 캐시 키 전략 개선"
                    })
                    suggestions["overall_health"] = "needs_improvement"
                
                if avg_time > 100:  # 100ms 이상
                    suggestions["ttl_adjustments"].append({
                        "cache": cache_type,
                        "current_performance": f"{avg_time:.0f}ms",
                        "recommendation": "캐시 미스 시 성능이 느림, 예열 전략 고려"
                    })
        
        return suggestions
    
    # === 내부 헬퍼 함수 ===
    
    def _calculate_percentile(self, sorted_list: List[float], percentile: int) -> float:
        """백분위수 계산"""
        if not sorted_list:
            return 0
        
        index = int((percentile / 100) * len(sorted_list))
        if index >= len(sorted_list):
            index = len(sorted_list) - 1
        
        return sorted_list[index]
    
    def _get_recommendations(self, operation: str, avg_time: float) -> List[str]:
        """작업별 최적화 권장사항"""
        recommendations = []
        
        if "embedding" in operation:
            if avg_time > 300:
                recommendations.append("임베딩 캐시 TTL 증가")
                recommendations.append("배치 처리 고려")
        
        if "vector" in operation:
            if avg_time > 500:
                recommendations.append("벡터 인덱스 최적화")
                recommendations.append("검색 범위 축소")
        
        if "enrich" in operation:
            if avg_time > 200:
                recommendations.append("메타데이터 캐싱 강화")
                recommendations.append("병렬 처리 적용")
        
        return recommendations
    
    def _analyze_cache_performance(self, operation: str) -> Dict[str, Any]:
        """캐시 성능 분석"""
        # 실제로는 캐시 히트/미스 통계를 추적해야 함
        # 여기서는 간단한 시뮬레이션
        times = self.operation_times.get(operation, [])
        
        if not times:
            return {}
        
        # 캐시 히트는 일반적으로 더 빠름
        fast_times = [t for t in times if t < 50]  # 50ms 미만을 캐시 히트로 가정
        hit_rate = len(fast_times) / len(times) if times else 0
        
        return {
            "hit_rate": hit_rate,
            "average_time": sum(times) / len(times),
            "cache_hits": len(fast_times),
            "cache_misses": len(times) - len(fast_times)
        }
