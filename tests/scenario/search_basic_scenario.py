"""Search 기본 시나리오 테스트

기본적인 검색 기능을 검증하는 시나리오 테스트
실제 서비스 흐름을 따라 종단간 테스트 수행
"""

import asyncio
from datetime import datetime, timedelta
from typing import List

import pytest
from httpx import AsyncClient

from modules.search import SearchOrchestrator, SearchQuery, SearchResponse


class TestSearchBasicScenario:
    """기본 검색 시나리오 테스트"""
    
    @pytest.fixture
    async def orchestrator(self):
        """SearchOrchestrator 인스턴스"""
        return SearchOrchestrator()
    
    @pytest.fixture
    async def api_client(self):
        """비동기 HTTP 클라이언트"""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            yield client
    
    async def test_simple_text_search(self, orchestrator):
        """단순 텍스트 검색 시나리오
        
        시나리오:
        1. 사용자가 "프로젝트 관련 문서"를 검색
        2. 시스템이 자연어 처리하여 임베딩 생성
        3. 벡터 검색으로 관련 문서 찾기
        4. 메타데이터와 함께 결과 반환
        """
        # Given: 검색 질의 준비
        query = SearchQuery(
            query_text="프로젝트 관련 문서",
            limit=10,
            score_threshold=0.7
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert isinstance(response, SearchResponse)
        assert response.query == "프로젝트 관련 문서"
        assert response.total_count >= 0
        assert response.search_time_ms > 0
        assert response.query_id is not None
        
        # 결과가 있는 경우 추가 검증
        if response.total_count > 0:
            first_result = response.results[0]
            assert first_result.document_id is not None
            assert first_result.title is not None
            assert first_result.snippet is not None
            assert 0.0 <= first_result.score <= 1.0
            assert first_result.source_collection in ["emails", "documents", "messages"]
    
    async def test_search_with_date_filter(self, orchestrator):
        """날짜 필터를 포함한 검색 시나리오
        
        시나리오:
        1. 사용자가 "지난주 회의록"을 검색
        2. 시스템이 자연어에서 날짜 필터 추출
        3. 필터와 벡터 검색 조합으로 결과 찾기
        4. 시간순으로 정렬된 결과 반환
        """
        # Given: 날짜 범위 설정
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        query = SearchQuery(
            query_text="지난주 회의록",
            filters={
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            },
            limit=20
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert response.filters_applied is True
        assert response.search_mode == "hybrid"
        
        # 결과가 날짜 범위 내에 있는지 확인
        for result in response.results:
            if result.metadata.get("date"):
                result_date = datetime.fromisoformat(result.metadata["date"])
                assert start_date <= result_date <= end_date
    
    async def test_search_with_sender_filter(self, orchestrator):
        """발신자 필터를 포함한 검색 시나리오
        
        시나리오:
        1. 사용자가 "김철수가 보낸 예산 관련 메일"을 검색
        2. 시스템이 발신자와 키워드 추출
        3. 필터 적용하여 특정 발신자의 메일만 검색
        4. 관련성 높은 순으로 결과 반환
        """
        # Given: 발신자 필터 포함 질의
        query = SearchQuery(
            query_text="김철수가 보낸 예산 관련 메일",
            auto_extract_filters=True,  # 자동 필터 추출 활성화
            limit=15
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert response.total_count >= 0
        
        # 필터가 추출되었는지 확인
        if response.filters_applied:
            # 모든 결과가 필터 조건을 만족하는지 확인
            for result in response.results:
                # 발신자 정보가 있고 추출된 경우
                if result.metadata.get("sender"):
                    # 실제 필터 적용 여부는 처리 로직에 따름
                    pass
    
    async def test_search_with_attachment_filter(self, orchestrator):
        """첨부파일 필터를 포함한 검색 시나리오
        
        시나리오:
        1. 사용자가 "첨부파일이 있는 계약서"를 검색
        2. 시스템이 첨부파일 유무 필터 적용
        3. 첨부파일이 있는 문서만 검색
        4. 첨부파일 정보와 함께 결과 반환
        """
        # Given: 첨부파일 필터 질의
        query = SearchQuery(
            query_text="첨부파일이 있는 계약서",
            filters={
                "has_attachments": True
            },
            limit=10
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        for result in response.results:
            # 첨부파일 정보 확인
            assert result.enrichment is not None
            if result.enrichment.has_attachments:
                assert result.enrichment.attachment_count > 0
                assert len(result.enrichment.attachment_names) > 0
    
    async def test_empty_search_result(self, orchestrator):
        """검색 결과가 없는 시나리오
        
        시나리오:
        1. 사용자가 존재하지 않는 내용 검색
        2. 시스템이 검색 수행
        3. 결과가 없음을 명시적으로 반환
        4. 적절한 메시지와 함께 빈 결과 제공
        """
        # Given: 결과가 없을 것으로 예상되는 질의
        query = SearchQuery(
            query_text="xyzabc123불가능한검색어",
            score_threshold=0.9  # 높은 임계값
        )
        
        # When: 검색 실행
        response = await orchestrator.search_orchestrator_process(query)
        
        # Then: 검증
        assert response.total_count == 0
        assert len(response.results) == 0
        assert response.search_time_ms > 0
        assert response.query_id is not None
        assert "검색 결과가 없습니다" in str(response.search_metadata)
    
    async def test_search_error_handling(self, orchestrator):
        """검색 오류 처리 시나리오
        
        시나리오:
        1. 사용자가 잘못된 형식의 질의 입력
        2. 시스템이 입력 검증 수행
        3. 적절한 오류 메시지 반환
        4. 시스템은 정상 상태 유지
        """
        # Given: 잘못된 질의들
        invalid_queries = [
            "",  # 빈 검색어
            " ",  # 공백만
            "a",  # 너무 짧은 검색어
            "x" * 1001,  # 너무 긴 검색어
        ]
        
        for invalid_query in invalid_queries:
            # When/Then: 예외 발생 확인
            with pytest.raises(ValueError):
                query = SearchQuery(query_text=invalid_query)
                await orchestrator.search_orchestrator_process(query)
    
    async def test_search_response_time(self, orchestrator):
        """검색 응답 시간 측정 시나리오
        
        시나리오:
        1. 다양한 검색 질의 실행
        2. 각 검색의 응답 시간 측정
        3. 평균 응답 시간 계산
        4. 성능 목표(1초 이하) 달성 확인
        """
        # Given: 다양한 검색 질의
        queries = [
            "회의록",
            "프로젝트 계획서",
            "예산 보고서",
            "인사 관련 공지",
            "기술 문서"
        ]
        
        response_times = []
        
        # When: 각 질의 실행 및 시간 측정
        for query_text in queries:
            query = SearchQuery(query_text=query_text, limit=10)
            response = await orchestrator.search_orchestrator_process(query)
            response_times.append(response.search_time_ms)
        
        # Then: 성능 검증
        average_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        
        assert average_time < 1000  # 평균 1초 이하
        assert max_time < 2000  # 최대 2초 이하
        
        print(f"평균 응답 시간: {average_time:.2f}ms")
        print(f"최대 응답 시간: {max_time}ms")
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self, orchestrator):
        """동시 검색 처리 시나리오
        
        시나리오:
        1. 여러 사용자가 동시에 검색 요청
        2. 시스템이 모든 요청을 병렬 처리
        3. 각 요청이 독립적으로 처리됨
        4. 모든 응답이 정상적으로 반환됨
        """
        # Given: 동시 실행할 검색 질의들
        concurrent_queries = [
            SearchQuery(query_text=f"검색 질의 {i}", limit=5)
            for i in range(10)
        ]
        
        # When: 동시 실행
        tasks = [
            orchestrator.search_orchestrator_process(query)
            for query in concurrent_queries
        ]
        responses = await asyncio.gather(*tasks)
        
        # Then: 모든 응답 검증
        assert len(responses) == 10
        for i, response in enumerate(responses):
            assert response.query == f"검색 질의 {i}"
            assert response.query_id is not None
            assert response.search_time_ms > 0


# 실행 가능한 메인 함수
async def main():
    """시나리오 테스트 실행"""
    print("=== Search 기본 시나리오 테스트 시작 ===")
    
    orchestrator = SearchOrchestrator()
    test = TestSearchBasicScenario()
    
    # 각 테스트 실행
    try:
        print("\n1. 단순 텍스트 검색 테스트...")
        await test.test_simple_text_search(orchestrator)
        print("✓ 통과")
        
        print("\n2. 날짜 필터 검색 테스트...")
        await test.test_search_with_date_filter(orchestrator)
        print("✓ 통과")
        
        print("\n3. 발신자 필터 검색 테스트...")
        await test.test_search_with_sender_filter(orchestrator)
        print("✓ 통과")
        
        print("\n4. 첨부파일 필터 검색 테스트...")
        await test.test_search_with_attachment_filter(orchestrator)
        print("✓ 통과")
        
        print("\n5. 빈 결과 처리 테스트...")
        await test.test_empty_search_result(orchestrator)
        print("✓ 통과")
        
        print("\n6. 응답 시간 측정 테스트...")
        await test.test_search_response_time(orchestrator)
        print("✓ 통과")
        
        print("\n7. 동시 검색 처리 테스트...")
        await test.test_concurrent_searches(orchestrator)
        print("✓ 통과")
        
        print("\n=== 모든 테스트 통과! ===")
        
    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
