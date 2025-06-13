"""Search 벡터 검색 서비스

Qdrant를 사용한 벡터 유사도 검색
순수 벡터 검색 및 다중 컬렉션 지원
"""

import asyncio
from typing import Any, Dict, List, Optional, Set

import structlog
from qdrant_client.models import Filter, FieldCondition, Match, Range

from infra.vector_store import VectorStoreManager, get_vector_manager

from .schema import (
    CollectionStrategy,
    SearchFilters,
    SearchMode,
    SearchQuery,
    VectorMatch,
    DateRange
)

logger = structlog.get_logger(__name__)


class SearchVectorService:
    """벡터 검색 전용 서비스"""
    
    def __init__(self):
        """SearchVectorService 초기화 - 의존성 없이 생성"""
        self.vector_manager: Optional[VectorStoreManager] = None
        self.repository: Optional['SearchRepository'] = None
        self._initialized = False
        
        # 기본 설정
        self.default_collection = "emails"
        self.available_collections = ["emails", "documents", "messages"]
        self.max_limit = 100
        self.default_score_threshold = 0.7
        
        # 컬렉션별 가중치 (다중 컬렉션 검색 시 사용)
        self.collection_weights = {
            "emails": 1.0,
            "documents": 0.9,
            "messages": 0.8
        }
    
    async def set_dependencies(self, **kwargs) -> None:
        """Orchestrator에서 의존성 주입
        
        Args:
            repository: 리포지토리 인스턴스 (선택적)
        """
        if 'repository' in kwargs:
            self.repository = kwargs['repository']
        self._initialized = True
        logger.debug("SearchVectorService 의존성 주입 완료")
    
    def _ensure_dependencies(self) -> None:
        """의존성 주입 확인"""
        if not self._initialized:
            raise RuntimeError("SearchVectorService: 의존성이 주입되지 않았습니다. set_dependencies()를 먼저 호출하세요.")
    
    # === 메인 검색 함수 ===
    
    async def search_vector_find(
        self,
        embedding: List[float],
        query: SearchQuery
    ) -> List[VectorMatch]:
        """검색 모드에 따른 벡터 검색
        
        Args:
            embedding: 검색 임베딩
            query: 검색 질의 정보
            
        Returns:
            벡터 매치 결과 목록
        """
        self._ensure_dependencies()
        
        # vector_manager는 직접 가져옴 (싱글톤)
        if not self.vector_manager:
            self.vector_manager = get_vector_manager()
        
        try:
            # 검색 모드별 분기
            if query.search_mode == SearchMode.VECTOR_ONLY:
                # 순수 벡터 검색
                results = await self.search_vector_find_pure(
                    embedding=embedding,
                    collections=query.target_collections or [self.default_collection],
                    limit=query.limit,
                    score_threshold=query.score_threshold
                )
            elif query.search_mode == SearchMode.FILTER_ONLY:
                # 필터만 사용 (벡터 검색 없음)
                logger.warning("FILTER_ONLY 모드는 벡터 서비스에서 지원하지 않습니다")
                return []
            else:  # HYBRID
                # 하이브리드 검색 (필터 + 벡터)
                collections = await self.search_vector_select_collections(
                    query.collection_strategy,
                    query.target_collections
                )
                results = await self.search_vector_find_with_filters(
                    embedding=embedding,
                    filters=query.filters,
                    collections=collections,
                    limit=query.limit
                )
            
            # 점수 임계값 적용
            if query.score_threshold:
                results = await self.search_vector_apply_score_threshold(
                    results, query.score_threshold
                )
            
            logger.info(
                "벡터 검색 완료",
                mode=query.search_mode.value,
                result_count=len(results),
                top_score=results[0].score if results else 0
            )
            
            return results
            
        except Exception as e:
            logger.error("벡터 검색 실패", error=str(e))
            raise
    
    # === 순수 벡터 검색 ===
    
    async def search_vector_find_pure(
        self,
        embedding: List[float],
        collections: List[str],
        limit: int,
        score_threshold: float
    ) -> List[VectorMatch]:
        """순수 벡터 검색 (필터 없음)
        
        Args:
            embedding: 검색 임베딩
            collections: 검색할 컬렉션 목록
            limit: 결과 개수 제한
            score_threshold: 점수 임계값
            
        Returns:
            벡터 매치 결과 목록
        """
        logger.debug(
            "순수 벡터 검색 시작",
            collections=collections,
            limit=limit,
            threshold=score_threshold
        )
        
        # 다중 컬렉션 검색
        if len(collections) > 1:
            return await self.search_vector_search_multiple_collections(
                embedding=embedding,
                collections=collections,
                filters=None,
                limit=limit
            )
        
        # 단일 컬렉션 검색
        collection = collections[0]
        results = await self.vector_manager.search_vectors(
            query_vector=embedding,
            collection=collection,
            filters=None,
            limit=limit,
            score_threshold=score_threshold
        )
        
        # VectorMatch로 변환
        return [
            VectorMatch(
                document_id=match.id,
                score=match.score,
                metadata=match.payload,
                collection_name=collection
            )
            for match in results
        ]
    
    # === 필터 포함 검색 ===
    
    async def search_vector_find_with_filters(
        self,
        embedding: List[float],
        filters: Optional[SearchFilters],
        collections: List[str],
        limit: int
    ) -> List[VectorMatch]:
        """하이브리드 검색 (필터 + 벡터)
        
        Args:
            embedding: 검색 임베딩
            filters: 검색 필터
            collections: 검색할 컬렉션 목록
            limit: 결과 개수 제한
            
        Returns:
            벡터 매치 결과 목록
        """
        logger.debug(
            "하이브리드 검색 시작",
            collections=collections,
            has_filters=filters is not None,
            limit=limit
        )
        
        # 다중 컬렉션 검색
        if len(collections) > 1:
            return await self.search_vector_search_multiple_collections(
                embedding=embedding,
                collections=collections,
                filters=filters,
                limit=limit
            )
        
        # 단일 컬렉션 검색
        collection = collections[0]
        
        # Qdrant 필터 빌드
        qdrant_filter = None
        if filters:
            qdrant_filter = await self.search_vector_build_filter(filters)
        
        # 벡터 검색 실행
        results = await self.vector_manager.search_vectors(
            query_vector=embedding,
            collection=collection,
            filters=self._convert_to_infra_filters(filters) if filters else None,
            limit=limit
        )
        
        # VectorMatch로 변환
        return [
            VectorMatch(
                document_id=match.id,
                score=match.score,
                metadata=match.payload,
                collection_name=collection
            )
            for match in results
        ]
    
    # === 컬렉션 선택 ===
    
    async def search_vector_select_collections(
        self,
        strategy: CollectionStrategy,
        target_collections: Optional[List[str]]
    ) -> List[str]:
        """컬렉션 선택 전략에 따른 컬렉션 목록 반환
        
        Args:
            strategy: 컬렉션 선택 전략
            target_collections: 대상 컬렉션 목록
            
        Returns:
            선택된 컬렉션 목록
        """
        if strategy == CollectionStrategy.SINGLE:
            # 단일 컬렉션 (기본값)
            return [self.default_collection]
            
        elif strategy == CollectionStrategy.MULTIPLE:
            # 지정된 여러 컬렉션
            if target_collections:
                # 유효한 컬렉션만 필터링
                valid_collections = [
                    c for c in target_collections 
                    if c in self.available_collections
                ]
                return valid_collections or [self.default_collection]
            return [self.default_collection]
            
        elif strategy == CollectionStrategy.AUTO:
            # 자동 선택 (추후 구현 - 현재는 모든 컬렉션)
            return self.available_collections
            
        else:
            return [self.default_collection]
    
    async def search_vector_get_available_collections(self) -> List[str]:
        """사용 가능한 컬렉션 목록 반환
        
        Returns:
            컬렉션 이름 목록
        """
        # 실제로는 Qdrant에서 조회해야 하지만, 현재는 하드코딩
        return self.available_collections
    
    # === 다중 컬렉션 검색 ===
    
    async def search_vector_search_multiple_collections(
        self,
        embedding: List[float],
        collections: List[str],
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[VectorMatch]:
        """여러 컬렉션에서 병렬 검색
        
        Args:
            embedding: 검색 임베딩
            collections: 검색할 컬렉션 목록
            filters: 검색 필터
            limit: 컬렉션당 결과 개수 제한
            
        Returns:
            통합된 검색 결과
        """
        logger.debug(
            "다중 컬렉션 검색 시작",
            collections=collections,
            limit_per_collection=limit
        )
        
        # 각 컬렉션별 검색 태스크 생성
        tasks = []
        for collection in collections:
            task = self._search_single_collection(
                embedding=embedding,
                collection=collection,
                filters=filters,
                limit=limit
            )
            tasks.append(task)
        
        # 병렬 실행
        collection_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 딕셔너리 생성
        results_dict = {}
        for collection, result in zip(collections, collection_results):
            if isinstance(result, Exception):
                logger.warning(
                    "컬렉션 검색 실패",
                    collection=collection,
                    error=str(result)
                )
                results_dict[collection] = []
            else:
                results_dict[collection] = result
        
        # 결과 병합 및 정렬
        return await self.search_vector_merge_collection_results(
            results_dict, limit
        )
    
    async def search_vector_merge_collection_results(
        self,
        collection_results: Dict[str, List[VectorMatch]],
        limit: int
    ) -> List[VectorMatch]:
        """컬렉션별 결과를 병합하고 정렬
        
        Args:
            collection_results: 컬렉션별 검색 결과
            limit: 최종 결과 개수 제한
            
        Returns:
            병합된 검색 결과
        """
        # 모든 결과 수집
        all_matches = []
        
        for collection_name, matches in collection_results.items():
            if isinstance(matches, list):
                # 컬렉션 가중치 적용
                weight = self.collection_weights.get(collection_name, 1.0)
                
                for match in matches:
                    # 가중치 적용된 점수
                    match.weighted_score = match.score * weight
                    match.collection_name = collection_name
                    all_matches.append(match)
        
        # 점수 정규화
        normalized_matches = await self._search_vector_normalize_scores_across_collections(
            all_matches
        )
        
        # 중복 제거
        unique_matches = await self._search_vector_deduplicate(normalized_matches)
        
        # 점수 기준 정렬
        sorted_matches = await self._search_vector_sort_by_relevance(unique_matches)
        
        # 결과 개수 제한
        return sorted_matches[:limit]
    
    # === 필터 처리 ===
    
    async def search_vector_build_filter(
        self,
        filters: SearchFilters
    ) -> Optional[Filter]:
        """SearchFilters를 Qdrant Filter로 변환
        
        Args:
            filters: 검색 필터
            
        Returns:
            Qdrant Filter 또는 None
        """
        conditions = []
        
        # 날짜 범위 필터
        if filters.date_range:
            conditions.append(
                FieldCondition(
                    key="date",
                    range=Range(
                        gte=filters.date_range.start_date.isoformat(),
                        lte=filters.date_range.end_date.isoformat()
                    )
                )
            )
        
        # 발신자 필터
        if filters.sender:
            conditions.append(
                FieldCondition(
                    key="sender",
                    match=Match(value=filters.sender)
                )
            )
        
        # 수신자 필터
        if filters.recipients:
            conditions.append(
                FieldCondition(
                    key="recipients",
                    match=Match(any=filters.recipients)
                )
            )
        
        # 첨부파일 필터
        if filters.has_attachments is not None:
            conditions.append(
                FieldCondition(
                    key="has_attachments",
                    match=Match(value=filters.has_attachments)
                )
            )
        
        # 제목 키워드 필터
        if filters.subject_keywords:
            for keyword in filters.subject_keywords:
                conditions.append(
                    FieldCondition(
                        key="subject",
                        match=Match(text=keyword)
                    )
                )
        
        # 스레드 ID 필터
        if filters.thread_id:
            conditions.append(
                FieldCondition(
                    key="thread_id",
                    match=Match(value=filters.thread_id)
                )
            )
        
        return Filter(must=conditions) if conditions else None
    
    async def search_vector_apply_score_threshold(
        self,
        matches: List[VectorMatch],
        threshold: float
    ) -> List[VectorMatch]:
        """점수 임계값 적용
        
        Args:
            matches: 검색 결과
            threshold: 점수 임계값
            
        Returns:
            필터링된 결과
        """
        filtered = [m for m in matches if m.score >= threshold]
        
        logger.debug(
            "점수 임계값 적용",
            threshold=threshold,
            before_count=len(matches),
            after_count=len(filtered)
        )
        
        return filtered
    
    # === 내부 헬퍼 함수 ===
    
    async def _search_single_collection(
        self,
        embedding: List[float],
        collection: str,
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[VectorMatch]:
        """단일 컬렉션 검색 헬퍼"""
        try:
            # infra 레이어 호출
            results = await self.vector_manager.search_vectors(
                query_vector=embedding,
                collection=collection,
                filters=self._convert_to_infra_filters(filters) if filters else None,
                limit=limit
            )
            
            # VectorMatch로 변환
            return [
                VectorMatch(
                    document_id=match.id,
                    score=match.score,
                    metadata=match.payload,
                    collection_name=collection
                )
                for match in results
            ]
            
        except Exception as e:
            logger.error(
                "단일 컬렉션 검색 실패",
                collection=collection,
                error=str(e)
            )
            return []
    
    def _convert_to_infra_filters(
        self,
        filters: SearchFilters
    ) -> 'infra.vector_store.SearchFilters':
        """모듈 필터를 infra 필터로 변환"""
        from infra.vector_store import SearchFilters as InfraSearchFilters
        
        # 날짜 변환
        date_start = None
        date_end = None
        if filters.date_range:
            date_start = filters.date_range.start_date.strftime("%Y-%m-%d")
            date_end = filters.date_range.end_date.strftime("%Y-%m-%d")
        
        return InfraSearchFilters(
            sender_address=filters.sender,
            has_attachments=filters.has_attachments,
            thread_id=filters.thread_id,
            received_date_start=date_start,
            received_date_end=date_end
        )
    
    async def _search_vector_deduplicate(
        self,
        matches: List[VectorMatch]
    ) -> List[VectorMatch]:
        """중복 결과 제거"""
        seen_ids = set()
        unique_matches = []
        
        for match in matches:
            if match.document_id not in seen_ids:
                seen_ids.add(match.document_id)
                unique_matches.append(match)
        
        return unique_matches
    
    async def _search_vector_sort_by_relevance(
        self,
        matches: List[VectorMatch]
    ) -> List[VectorMatch]:
        """관련성 기준 정렬"""
        # weighted_score가 있으면 그것으로, 없으면 score로 정렬
        return sorted(
            matches,
            key=lambda m: getattr(m, 'weighted_score', m.score),
            reverse=True
        )
    
    async def _search_vector_normalize_scores_across_collections(
        self,
        matches: List[VectorMatch]
    ) -> List[VectorMatch]:
        """컬렉션간 점수 정규화"""
        if not matches:
            return matches
        
        # 컬렉션별 최대/최소 점수 계산
        collection_stats = {}
        for match in matches:
            collection = match.collection_name
            if collection not in collection_stats:
                collection_stats[collection] = {
                    'min': float('inf'),
                    'max': float('-inf'),
                    'matches': []
                }
            
            score = getattr(match, 'weighted_score', match.score)
            collection_stats[collection]['min'] = min(
                collection_stats[collection]['min'], score
            )
            collection_stats[collection]['max'] = max(
                collection_stats[collection]['max'], score
            )
            collection_stats[collection]['matches'].append(match)
        
        # 정규화 적용
        normalized_matches = []
        for collection, stats in collection_stats.items():
            min_score = stats['min']
            max_score = stats['max']
            score_range = max_score - min_score
            
            for match in stats['matches']:
                if score_range > 0:
                    # Min-Max 정규화
                    original_score = getattr(match, 'weighted_score', match.score)
                    normalized_score = (original_score - min_score) / score_range
                    match.normalized_score = normalized_score
                else:
                    match.normalized_score = 1.0
                
                normalized_matches.append(match)
        
        return normalized_matches
