"""Search 순수 벡터 검색 시나리오 테스트

필터 없이 의미적 유사도만으로 검색하는 기능을 검증
벡터 검색과 하이브리드 검색의 차이점을 비교
"""

import asyncio
from typing import List, Set

import pytest

from modules.search import SearchOrchestrator, SearchQuery, SearchResponse


class TestSearchVectorOnlyScenario:
    """순수 벡터 검색 시나리오 테스트"""
    
    @pytest.fixture
    async def orchestrator(self):
        """SearchOrchestrator 인스턴스"""
        return SearchOrchestrator()
    
    async def test_pure_vector_search(self, orchestrator):
        """순수 벡터 검색 기본 시나리오
        
        시나리오:
        1. 필터 없이 순수하게 의미적 유사도로만 검색
        2. 더 넓은 범위의 관련 문서 발견
        3. 탐색적 검색에 유용함을 확인
        """
        # Given: 순수 벡터 검색 모드 설정
        query = SearchQuery(
            query_text="인공지능 기술 동향",
            search_mode="vector_only",
            limit=20,
            score_threshold=0.6  # 더 낮은 임계값으로 더 많은 결과
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert response.search_mode == "vector_only"
        assert response.filters_applied is False
        assert response.total_count >= 0
        
        # 순수 벡터 검색은 더 다양한 결과 반환
        if response.total_count > 0:
            # 점수 분포 확인
            scores = [result.score for result in response.results]
            assert all(0.6 <= score <= 1.0 for score in scores)
            
            # 점수 순으로 정렬되어 있는지 확인
            assert scores == sorted(scores, reverse=True)
    
    async def test_vector_vs_hybrid_comparison(self, orchestrator):
        """순수 벡터 검색 vs 하이브리드 검색 비교
        
        시나리오:
        1. 동일한 질의로 두 가지 모드 검색 실행
        2. 결과 집합의 차이 분석
        3. 각 모드의 특성 확인
        """
        query_text = "프로젝트 일정 관리"
        
        # Given: 순수 벡터 검색
        vector_query = SearchQuery(
            query_text=query_text,
            search_mode="vector_only",
            limit=30,
            score_threshold=0.5
        )
        
        # Given: 하이브리드 검색
        hybrid_query = SearchQuery(
            query_text=query_text,
            search_mode="hybrid",
            limit=30,
            score_threshold=0.5,
            auto_extract_filters=True
        )
        
        # When: 두 검색 실행
        vector_response = await orchestrator.search_orchestrator_process(vector_query)
        hybrid_response = await orchestrator.search_orchestrator_process(hybrid_query)
        
        # Then: 결과 비교
        print(f"\n순수 벡터 검색 결과: {vector_response.total_count}개")
        print(f"하이브리드 검색 결과: {hybrid_response.total_count}개")
        
        # 벡터 검색이 일반적으로 더 많은 결과 반환
        assert vector_response.total_count >= hybrid_response.total_count
        
        # 결과 집합 차이 분석
        vector_ids = {r.document_id for r in vector_response.results}
        hybrid_ids = {r.document_id for r in hybrid_response.results}
        
        only_in_vector = vector_ids - hybrid_ids
        common_results = vector_ids & hybrid_ids
        
        print(f"벡터 검색에만 있는 결과: {len(only_in_vector)}개")
        print(f"공통 결과: {len(common_results)}개")
        
        # 메타데이터 확인
        assert "vector_only" in vector_response.search_metadata.get("search_strategy", "")
    
    async def test_exploratory_search(self, orchestrator):
        """탐색적 검색 시나리오
        
        시나리오:
        1. 모호하거나 광범위한 주제로 검색
        2. 순수 벡터 검색으로 관련 문서 폭넓게 탐색
        3. 예상치 못한 관련 문서 발견
        """
        # Given: 광범위한 주제
        exploratory_queries = [
            "혁신",
            "성장 전략",
            "디지털 트랜스포메이션",
            "팀워크와 협업"
        ]
        
        for query_text in exploratory_queries:
            query = SearchQuery(
                query_text=query_text,
                search_mode="vector_only",
                limit=15,
                score_threshold=0.5
            )
            
            # When: 검색 실행
            response = await orchestrator.search_orchestrator_process(query)
            
            # Then: 다양성 확인
            if response.total_count > 5:
                # 제목의 다양성 확인
                titles = [r.title for r in response.results[:5]]
                unique_titles = set(titles)
                
                # 대부분 서로 다른 제목
                assert len(unique_titles) >= 4
                
                # 컬렉션 다양성 확인
                collections = [r.source_collection for r in response.results]
                unique_collections = set(collections)
                
                print(f"\n'{query_text}' 검색 - 컬렉션 분포: {unique_collections}")
    
    async def test_semantic_similarity_search(self, orchestrator):
        """의미적 유사도 검색 시나리오
        
        시나리오:
        1. 동의어나 관련 개념으로 검색
        2. 정확한 키워드가 없어도 의미적으로 유사한 문서 검색
        3. 자연어 이해 능력 확인
        """
        # Given: 의미적으로 유사한 질의들
        semantic_groups = [
            {
                "concept": "회의",
                "queries": ["미팅", "회의", "모임", "브리핑", "토론"]
            },
            {
                "concept": "보고서",
                "queries": ["리포트", "보고서", "분석 문서", "결과 정리"]
            }
        ]
        
        for group in semantic_groups:
            concept = group["concept"]
            queries = group["queries"]
            
            all_results = {}
            
            # When: 각 동의어로 검색
            for query_text in queries:
                query = SearchQuery(
                    query_text=query_text,
                    search_mode="vector_only",
                    limit=10,
                    score_threshold=0.6
                )
                
                response = await orchestrator.search_orchestrator_process(query)
                all_results[query_text] = {
                    r.document_id for r in response.results
                }
            
            # Then: 결과 중첩도 확인
            # 의미적으로 유사한 질의들은 비슷한 결과를 반환해야 함
            for i, q1 in enumerate(queries[:-1]):
                for q2 in queries[i+1:]:
                    overlap = all_results[q1] & all_results[q2]
                    
                    # 최소한 일부는 겹쳐야 함
                    if all_results[q1] and all_results[q2]:
                        overlap_ratio = len(overlap) / min(
                            len(all_results[q1]), 
                            len(all_results[q2])
                        )
                        print(f"\n'{q1}' vs '{q2}' 중첩도: {overlap_ratio:.2%}")
                        assert overlap_ratio > 0.2  # 20% 이상 중첩
    
    async def test_low_score_threshold_search(self, orchestrator):
        """낮은 점수 임계값 검색 시나리오
        
        시나리오:
        1. 매우 낮은 점수 임계값으로 검색
        2. 약하게 관련된 문서까지 포함
        3. 재현율(recall) 최대화 확인
        """
        # Given: 낮은 임계값 설정
        query = SearchQuery(
            query_text="데이터 분석",
            search_mode="vector_only",
            limit=50,
            score_threshold=0.3  # 매우 낮은 임계값
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 많은 결과 반환 확인
        assert response.total_count > 20  # 많은 결과 기대
        
        # 점수 분포 분석
        if response.results:
            scores = [r.score for r in response.results]
            
            # 다양한 점수 범위
            high_scores = [s for s in scores if s >= 0.7]
            medium_scores = [s for s in scores if 0.5 <= s < 0.7]
            low_scores = [s for s in scores if 0.3 <= s < 0.5]
            
            print(f"\n점수 분포:")
            print(f"높음 (≥0.7): {len(high_scores)}개")
            print(f"중간 (0.5-0.7): {len(medium_scores)}개")
            print(f"낮음 (0.3-0.5): {len(low_scores)}개")
            
            # 낮은 점수의 결과도 포함되어야 함
            assert len(low_scores) > 0
    
    async def test_performance_comparison(self, orchestrator):
        """벡터 검색 성능 비교 시나리오
        
        시나리오:
        1. 순수 벡터 검색과 하이브리드 검색의 속도 비교
        2. 필터 처리가 없어 더 빠른 응답 확인
        3. 대량 검색 시 성능 이점 확인
        """
        query_text = "기술 혁신 트렌드"
        
        # Given: 동일한 질의로 여러 번 실행
        iterations = 5
        vector_times = []
        hybrid_times = []
        
        for _ in range(iterations):
            # 순수 벡터 검색
            vector_query = SearchQuery(
                query_text=query_text,
                search_mode="vector_only",
                limit=30
            )
            vector_response = await orchestrator.search_orchestrator_process(vector_query)
            vector_times.append(vector_response.search_time_ms)
            
            # 하이브리드 검색
            hybrid_query = SearchQuery(
                query_text=query_text,
                search_mode="hybrid",
                limit=30,
                auto_extract_filters=True
            )
            hybrid_response = await orchestrator.search_orchestrator_process(hybrid_query)
            hybrid_times.append(hybrid_response.search_time_ms)
        
        # Then: 성능 비교
        avg_vector_time = sum(vector_times) / len(vector_times)
        avg_hybrid_time = sum(hybrid_times) / len(hybrid_times)
        
        print(f"\n평균 응답 시간:")
        print(f"순수 벡터 검색: {avg_vector_time:.2f}ms")
        print(f"하이브리드 검색: {avg_hybrid_time:.2f}ms")
        print(f"속도 향상: {((avg_hybrid_time - avg_vector_time) / avg_hybrid_time * 100):.1f}%")
        
        # 일반적으로 순수 벡터 검색이 더 빨라야 함
        # (필터 처리가 없으므로)
        assert avg_vector_time <= avg_hybrid_time * 1.2  # 20% 여유


# 실행 가능한 메인 함수
async def main():
    """순수 벡터 검색 시나리오 테스트 실행"""
    print("=== Search 순수 벡터 검색 시나리오 테스트 시작 ===")
    
    orchestrator = SearchOrchestrator()
    test = TestSearchVectorOnlyScenario()
    
    try:
        print("\n1. 순수 벡터 검색 기본 테스트...")
        await test.test_pure_vector_search(orchestrator)
        print("✓ 통과")
        
        print("\n2. 벡터 vs 하이브리드 비교 테스트...")
        await test.test_vector_vs_hybrid_comparison(orchestrator)
        print("✓ 통과")
        
        print("\n3. 탐색적 검색 테스트...")
        await test.test_exploratory_search(orchestrator)
        print("✓ 통과")
        
        print("\n4. 의미적 유사도 검색 테스트...")
        await test.test_semantic_similarity_search(orchestrator)
        print("✓ 통과")
        
        print("\n5. 낮은 임계값 검색 테스트...")
        await test.test_low_score_threshold_search(orchestrator)
        print("✓ 통과")
        
        print("\n6. 성능 비교 테스트...")
        await test.test_performance_comparison(orchestrator)
        print("✓ 통과")
        
        print("\n=== 모든 테스트 통과! ===")
        
    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
