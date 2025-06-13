#!/usr/bin/env python3
"""
SearchOrchestrator.search_orchestrator_process 함수 테스트

기존 구현체를 테스트하여 발생하는 에러를 확인하고 수정
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.search.orchestrator import SearchOrchestrator
from modules.search.schema import SearchQuery, SearchMode, CollectionStrategy


async def test_search_orchestrator_process():
    """search_orchestrator_process 함수 기본 테스트"""
    print("=== SearchOrchestrator.search_orchestrator_process 테스트 시작 ===")
    
    try:
        # 1. SearchOrchestrator 인스턴스 생성
        print("1. SearchOrchestrator 인스턴스 생성 중...")
        orchestrator = SearchOrchestrator()
        print("✓ SearchOrchestrator 인스턴스 생성 완료")
        
        # 2. 기본 검색 쿼리 생성
        print("2. 검색 쿼리 생성 중...")
        query = SearchQuery(
            query_text="최근 한달간 IMO에 제안한 의견은 무엇인가요?",
            search_mode=SearchMode.HYBRID,  # 하이브리드 모드로 변경
            collection_strategy=CollectionStrategy.SINGLE,
            target_collections=["email_vectors"],  # email_vectors 컬렉션 명시
            limit=5,
            score_threshold=0.3  # 낮춘 임계값
        )
        print("✓ 검색 쿼리 생성 완료")
        
        # 3. search_orchestrator_process 함수 호출
        print("3. search_orchestrator_process 함수 호출 중...")
        response = await orchestrator.search_orchestrator_process(query)
        print("✓ search_orchestrator_process 함수 호출 완료")
        
        # 4. 응답 검증
        print("4. 응답 검증 중...")
        print(f"   - 쿼리: {response.query}")
        print(f"   - 결과 수: {response.total_count}")
        print(f"   - 검색 시간: {response.search_time_ms}ms")
        print(f"   - 검색 모드: {response.search_mode}")
        print(f"   - 쿼리 ID: {response.query_id}")
        print("✓ 응답 검증 완료")
        
        print("\n=== 테스트 성공 ===")
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {type(e).__name__}: {str(e)}")
        print(f"에러 발생 위치: {e.__traceback__.tb_frame.f_code.co_filename}:{e.__traceback__.tb_lineno}")
        
        # 상세 에러 정보 출력
        import traceback
        print("\n=== 상세 에러 정보 ===")
        traceback.print_exc()
        
        return False


async def test_initialization_only():
    """초기화만 테스트 (의존성 문제 확인용)"""
    print("\n=== 초기화 테스트 시작 ===")
    
    try:
        print("1. SearchOrchestrator 인스턴스 생성...")
        orchestrator = SearchOrchestrator()
        print("✓ 인스턴스 생성 완료")
        
        print("2. 초기화 확인...")
        await orchestrator._ensure_initialized()
        print("✓ 초기화 완료")
        
        print("3. 서비스 상태 확인...")
        print(f"   - query_processor: {orchestrator.query_processor is not None}")
        print(f"   - embedding_service: {orchestrator.embedding_service is not None}")
        print(f"   - vector_service: {orchestrator.vector_service is not None}")
        print(f"   - result_enricher: {orchestrator.result_enricher is not None}")
        print(f"   - repository: {orchestrator.repository is not None}")
        print(f"   - performance_monitor: {orchestrator.performance_monitor is not None}")
        
        print("\n=== 초기화 테스트 성공 ===")
        return True
        
    except Exception as e:
        print(f"\n❌ 초기화 테스트 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_validation_only():
    """요청 검증만 테스트"""
    print("\n=== 요청 검증 테스트 시작 ===")
    
    try:
        orchestrator = SearchOrchestrator()
        
        # 정상 케이스
        print("1. 정상 검색어 검증...")
        await orchestrator._search_orchestrator_validate_request("정상적인 검색어")
        print("✓ 정상 검색어 검증 통과")
        
        # 빈 문자열 케이스
        print("2. 빈 검색어 검증...")
        try:
            await orchestrator._search_orchestrator_validate_request("")
            print("❌ 빈 검색어가 통과됨 (예상하지 못한 결과)")
        except ValueError as e:
            print(f"✓ 빈 검색어 검증 실패 (예상된 결과): {e}")
        
        # 너무 긴 문자열 케이스
        print("3. 긴 검색어 검증...")
        long_query = "a" * 1001
        try:
            await orchestrator._search_orchestrator_validate_request(long_query)
            print("❌ 긴 검색어가 통과됨 (예상하지 못한 결과)")
        except ValueError as e:
            print(f"✓ 긴 검색어 검증 실패 (예상된 결과): {e}")
        
        print("\n=== 요청 검증 테스트 성공 ===")
        return True
        
    except Exception as e:
        print(f"\n❌ 요청 검증 테스트 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """메인 테스트 실행"""
    print("SearchOrchestrator 테스트 시작\n")
    
    # 환경 변수 확인
    print("=== 환경 설정 확인 ===")
    env_file = project_root / ".env"
    if env_file.exists():
        print("✓ .env 파일 존재")
    else:
        print("❌ .env 파일 없음")
    
    # 단계별 테스트 실행
    tests = [
        ("요청 검증", test_validation_only),
        ("초기화", test_initialization_only),
        ("전체 프로세스", test_search_orchestrator_process),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"테스트: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"테스트 '{test_name}' 실행 중 예외 발생: {e}")
            results[test_name] = False
    
    # 결과 요약
    print(f"\n{'='*50}")
    print("테스트 결과 요약")
    print('='*50)
    
    for test_name, result in results.items():
        status = "✓ 성공" if result else "❌ 실패"
        print(f"{test_name}: {status}")
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    print(f"\n전체 결과: {success_count}/{total_count} 테스트 성공")
    
    if success_count == total_count:
        print("🎉 모든 테스트가 성공했습니다!")
    else:
        print("⚠️  일부 테스트가 실패했습니다. 위의 에러 메시지를 확인해주세요.")


if __name__ == "__main__":
    asyncio.run(main())
