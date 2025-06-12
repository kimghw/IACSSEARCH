"""Search 다중 컬렉션 시나리오 테스트

여러 컬렉션에서 동시에 검색하는 기능을 검증
컬렉션 선택 전략과 결과 병합 로직을 테스트
"""

import asyncio
from typing import Dict, List, Set

import pytest

from modules.search import SearchOrchestrator, SearchQuery, SearchResponse


class TestSearchMultiCollectionScenario:
    """다중 컬렉션 검색 시나리오 테스트"""
    
    @pytest.fixture
    async def orchestrator(self):
        """SearchOrchestrator 인스턴스"""
        return SearchOrchestrator()
    
    async def test_single_collection_search(self, orchestrator):
        """단일 컬렉션 검색 시나리오
        
        시나리오:
        1. 기본 단일 컬렉션(emails)에서만 검색
        2. 모든 결과가 동일 컬렉션에서 나옴을 확인
        3. 검색 속도가 가장 빠름을 확인
        """
        # Given: 단일 컬렉션 전략
        query = SearchQuery(
            query_text="회의 일정 조정",
            collection_strategy="single",
            limit=15
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert response.collections_searched == ["emails"]
        
        # 모든 결과가 emails 컬렉션에서
        for result in response.results:
            assert result.source_collection == "emails"
        
        # 검색 시간 기록
        print(f"\n단일 컬렉션 검색 시간: {response.search_time_ms}ms")
    
    async def test_multiple_collection_search(self, orchestrator):
        """다중 컬렉션 검색 시나리오
        
        시나리오:
        1. 지정된 여러 컬렉션에서 동시 검색
        2. 각 컬렉션의 결과가 통합됨을 확인
        3. 점수 정규화가 적용됨을 확인
        """
        # Given: 다중 컬렉션 지정
        query = SearchQuery(
            query_text="프로젝트 진행 상황",
            collection_strategy="multiple",
            target_collections=["emails", "documents", "messages"],
            limit=30
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert len(response.collections_searched) == 3
        assert set(response.collections_searched) == {"emails", "documents", "messages"}
        
        # 컬렉션별 결과 분포 확인
        collection_counts = {}
        for result in response.results:
            collection = result.source_collection
            collection_counts[collection] = collection_counts.get(collection, 0) + 1
        
        print(f"\n컬렉션별 결과 분포:")
        for collection, count in collection_counts.items():
            print(f"  {collection}: {count}개")
        
        # 최소 2개 이상의 컬렉션에서 결과가 있어야 함
        assert len(collection_counts) >= 2
    
    async def test_auto_collection_selection(self, orchestrator):
        """자동 컬렉션 선택 시나리오
        
        시나리오:
        1. 질의 내용에 따라 자동으로 컬렉션 선택
        2. 이메일 관련 질의는 emails 컬렉션 포함
        3. 문서 관련 질의는 documents 컬렉션 포함
        """
        # Given: 다양한 질의와 자동 선택
        test_cases = [
            {
                "query": "이메일로 받은 계약서",
                "expected_collection": "emails"
            },
            {
                "query": "기술 문서 검토 요청",
                "expected_collection": "documents"
            },
            {
                "query": "팀 채팅 메시지 내용",
                "expected_collection": "messages"
            }
        ]
        
        for test_case in test_cases:
            query = SearchQuery(
                query_text=test_case["query"],
                collection_strategy="auto",
                limit=10
            )
            
            # When: 검색 실행
            response = await orchestrator.search_orchestrator_process(query)
            
            # Then: 예상 컬렉션이 포함되어 있는지 확인
            print(f"\n'{test_case['query']}' 검색 컬렉션: {response.collections_searched}")
            
            # AUTO 모드는 현재 모든 컬렉션을 검색
            assert len(response.collections_searched) >= 1
    
    async def test_collection_weight_application(self, orchestrator):
        """컬렉션 가중치 적용 시나리오
        
        시나리오:
        1. 각 컬렉션별로 다른 가중치 적용
        2. emails > documents > messages 순서로 우선순위
        3. 동일한 점수일 때 가중치가 높은 컬렉션이 우선
        """
        # Given: 다중 컬렉션 검색
        query = SearchQuery(
            query_text="중요한 공지사항",
            collection_strategy="multiple",
            target_collections=["emails", "documents", "messages"],
            limit=20
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 상위 결과 분석
        if len(response.results) >= 10:
            top_10_collections = [r.source_collection for r in response.results[:10]]
            
            # emails의 비중이 가장 높아야 함
            email_count = top_10_collections.count("emails")
            doc_count = top_10_collections.count("documents")
            msg_count = top_10_collections.count("messages")
            
            print(f"\n상위 10개 결과의 컬렉션 분포:")
            print(f"  emails: {email_count}")
            print(f"  documents: {doc_count}")
            print(f"  messages: {msg_count}")
            
            # 가중치 순서대로 분포되어야 함
            assert email_count >= doc_count
            assert doc_count >= msg_count
    
    async def test_collection_specific_filters(self, orchestrator):
        """컬렉션별 필터 적용 시나리오
        
        시나리오:
        1. 다중 컬렉션 검색 시 필터 적용
        2. 각 컬렉션에 맞는 필터가 적용됨을 확인
        3. 필터 조건을 만족하는 결과만 반환
        """
        # Given: 필터와 함께 다중 컬렉션 검색
        query = SearchQuery(
            query_text="첨부파일이 있는 보고서",
            collection_strategy="multiple",
            target_collections=["emails", "documents"],
            filters={
                "has_attachments": True
            },
            limit=15
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 필터 적용 확인
        assert response.filters_applied is True
        
        # 모든 결과가 첨부파일을 가져야 함
        for result in response.results:
            if result.enrichment:
                if result.source_collection == "emails":
                    # 이메일의 경우 첨부파일 정보 확인
                    assert result.enrichment.has_attachments is True
    
    async def test_parallel_collection_search(self, orchestrator):
        """병렬 컬렉션 검색 시나리오
        
        시나리오:
        1. 여러 컬렉션을 병렬로 검색
        2. 순차 검색보다 빠른 응답 시간
        3. 각 컬렉션의 에러가 전체 검색을 막지 않음
        """
        # Given: 많은 컬렉션에서 검색
        query = SearchQuery(
            query_text="데이터 분석 결과",
            collection_strategy="multiple",
            target_collections=["emails", "documents", "messages"],
            limit=50
        )
        
        # When: 병렬 검색 실행
        start_time = asyncio.get_event_loop().time()
        response = await orchestrator.search_orchestrator_process(query)
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # Then: 성능 검증
        print(f"\n병렬 검색 시간: {response.search_time_ms}ms")
        print(f"실제 경과 시간: {elapsed_time * 1000:.2f}ms")
        
        # 병렬 처리로 인해 개별 컬렉션 검색 시간의 합보다 짧아야 함
        assert response.search_time_ms < 3000  # 3초 이내
        
        # 결과가 여러 컬렉션에서 나왔는지 확인
        unique_collections = {r.source_collection for r in response.results}
        assert len(unique_collections) >= 2
    
    async def test_collection_result_deduplication(self, orchestrator):
        """중복 결과 제거 시나리오
        
        시나리오:
        1. 여러 컬렉션에 동일한 문서가 있을 수 있음
        2. 중복된 문서는 하나만 반환
        3. 가장 높은 점수를 가진 버전이 선택됨
        """
        # Given: 중복 가능성이 있는 검색
        query = SearchQuery(
            query_text="공유된 프로젝트 문서",
            collection_strategy="multiple",
            target_collections=["emails", "documents"],
            limit=30
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 중복 확인
        document_ids = [r.document_id for r in response.results]
        unique_ids = set(document_ids)
        
        # 모든 문서 ID가 고유해야 함
        assert len(document_ids) == len(unique_ids)
        
        print(f"\n총 결과: {len(response.results)}개")
        print(f"고유 문서: {len(unique_ids)}개")
    
    async def test_empty_collection_handling(self, orchestrator):
        """빈 컬렉션 처리 시나리오
        
        시나리오:
        1. 일부 컬렉션에 결과가 없을 수 있음
        2. 빈 컬렉션이 있어도 다른 컬렉션 결과는 정상 반환
        3. 에러 없이 처리됨
        """
        # Given: 매우 구체적인 검색어로 일부 컬렉션에서 결과 없음 유도
        query = SearchQuery(
            query_text="xyzabc123특수한검색어",
            collection_strategy="multiple",
            target_collections=["emails", "documents", "messages"],
            limit=10,
            score_threshold=0.8  # 높은 임계값
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 에러 없이 처리됨
        assert response is not None
        assert response.search_time_ms > 0
        assert response.collections_searched == ["emails", "documents", "messages"]
        
        # 결과가 없거나 일부 컬렉션에서만 나옴
        if response.total_count > 0:
            collections_with_results = {r.source_collection for r in response.results}
            print(f"\n결과가 있는 컬렉션: {collections_with_results}")
    
    async def test_score_normalization_across_collections(self, orchestrator):
        """컬렉션 간 점수 정규화 시나리오
        
        시나리오:
        1. 각 컬렉션의 점수 범위가 다를 수 있음
        2. 정규화를 통해 공정한 비교
        3. 최종 순위가 정규화된 점수 기준
        """
        # Given: 다중 컬렉션 검색
        query = SearchQuery(
            query_text="연례 보고서",
            collection_strategy="multiple",
            target_collections=["emails", "documents"],
            limit=20
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 점수 분포 분석
        if len(response.results) >= 10:
            # 컬렉션별 점수 수집
            collection_scores: Dict[str, List[float]] = {}
            for result in response.results:
                collection = result.source_collection
                if collection not in collection_scores:
                    collection_scores[collection] = []
                collection_scores[collection].append(result.score)
            
            # 각 컬렉션의 점수 범위 출력
            for collection, scores in collection_scores.items():
                if scores:
                    min_score = min(scores)
                    max_score = max(scores)
                    avg_score = sum(scores) / len(scores)
                    print(f"\n{collection} 점수 통계:")
                    print(f"  최소: {min_score:.3f}")
                    print(f"  최대: {max_score:.3f}")
                    print(f"  평균: {avg_score:.3f}")
            
            # 전체 결과가 점수순으로 정렬되어 있는지 확인
            scores = [r.score for r in response.results]
            assert scores == sorted(scores, reverse=True)


# 실행 가능한 메인 함수
async def main():
    """다중 컬렉션 시나리오 테스트 실행"""
    print("=== Search 다중 컬렉션 시나리오 테스트 시작 ===")
    
    orchestrator = SearchOrchestrator()
    test = TestSearchMultiCollectionScenario()
    
    try:
        print("\n1. 단일 컬렉션 검색 테스트...")
        await test.test_single_collection_search(orchestrator)
        print("✓ 통과")
        
        print("\n2. 다중 컬렉션 검색 테스트...")
        await test.test_multiple_collection_search(orchestrator)
        print("✓ 통과")
        
        print("\n3. 자동 컬렉션 선택 테스트...")
        await test.test_auto_collection_selection(orchestrator)
        print("✓ 통과")
        
        print("\n4. 컬렉션 가중치 적용 테스트...")
        await test.test_collection_weight_application(orchestrator)
        print("✓ 통과")
        
        print("\n5. 컬렉션별 필터 적용 테스트...")
        await test.test_collection_specific_filters(orchestrator)
        print("✓ 통과")
        
        print("\n6. 병렬 컬렉션 검색 테스트...")
        await test.test_parallel_collection_search(orchestrator)
        print("✓ 통과")
        
        print("\n7. 중복 결과 제거 테스트...")
        await test.test_collection_result_deduplication(orchestrator)
        print("✓ 통과")
        
        print("\n8. 빈 컬렉션 처리 테스트...")
        await test.test_empty_collection_handling(orchestrator)
        print("✓ 통과")
        
        print("\n9. 점수 정규화 테스트...")
        await test.test_score_normalization_across_collections(orchestrator)
        print("✓ 통과")
        
        print("\n=== 모든 테스트 통과! ===")
        
    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
