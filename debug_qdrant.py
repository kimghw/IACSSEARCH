"""
Qdrant 컬렉션 디버깅 스크립트
실제 컬렉션 구조와 데이터를 확인
"""

import asyncio
from infra.vector_store import get_vector_manager
from infra.core import get_infra_core

async def debug_qdrant():
    """Qdrant 디버깅"""
    print("=== Qdrant 디버깅 시작 ===")
    
    # 1. InfraCore 초기화
    print("1. InfraCore 초기화 중...")
    infra = get_infra_core()
    await infra.ensure_initialized()
    print("✓ InfraCore 초기화 완료")
    
    # 2. VectorOperations 가져오기
    print("2. VectorOperations 인스턴스 가져오기...")
    vector_ops = get_vector_manager()
    print("✓ VectorOperations 인스턴스 획득")
    
    # 3. 모든 컬렉션 목록 조회
    print("3. 모든 컬렉션 조회 중...")
    try:
        collections = vector_ops.qdrant_client.get_collections()
        print(f"✓ 발견된 컬렉션 수: {len(collections.collections)}")
        for collection in collections.collections:
            print(f"  - {collection.name}")
    except Exception as e:
        print(f"✗ 컬렉션 조회 실패: {e}")
        return
    
    # 4. email_vectors 컬렉션 상세 정보
    print("4. email_vectors 컬렉션 상세 정보...")
    try:
        collection_info = vector_ops.qdrant_client.get_collection("email_vectors")
        print(f"  - 벡터 수: {collection_info.vectors_count}")
        print(f"  - 인덱싱된 벡터 수: {collection_info.indexed_vectors_count}")
        print(f"  - 포인트 수: {collection_info.points_count}")
        print(f"  - 상태: {collection_info.status}")
        
        # 벡터 설정 정보
        vectors_config = collection_info.config.params.vectors
        if hasattr(vectors_config, 'size'):
            # Single vector
            print(f"  - 벡터 차원: {vectors_config.size}")
            print(f"  - 거리 메트릭: {vectors_config.distance}")
        else:
            # Named vectors
            print("  - Named Vectors 구조:")
            for name, config in vectors_config.items():
                print(f"    - {name}: {config.size}차원, {config.distance}")
                
    except Exception as e:
        print(f"✗ 컬렉션 정보 조회 실패: {e}")
        return
    
    # 5. 샘플 데이터 조회 (임계값 없이)
    print("5. 샘플 데이터 조회 중...")
    try:
        # 더미 벡터로 검색 (임계값 없이)
        dummy_vector = [0.1] * 1536  # OpenAI 임베딩 차원
        
        # Named vector 사용해서 검색
        try:
            results = vector_ops.qdrant_client.search(
                collection_name="email_vectors",
                query_vector=("body", dummy_vector),
                limit=3,
                score_threshold=0.0,  # 임계값 제거
                with_payload=True
            )
            print(f"  - Named vector 'body' 검색 결과: {len(results)}개")
            for i, result in enumerate(results):
                print(f"    [{i}] ID: {result.id}, Score: {result.score:.4f}")
                if result.payload:
                    keys = list(result.payload.keys())[:3]
                    print(f"        Payload keys: {keys}")
        except Exception as e:
            print(f"  - Named vector 'body' 검색 실패: {e}")
            
            # 다른 named vector 이름들 시도
            for vector_name in ["content", "text", "embedding", "vector", "body_vector"]:
                try:
                    results = vector_ops.qdrant_client.search(
                        collection_name="email_vectors",
                        query_vector=(vector_name, dummy_vector),
                        limit=3,
                        score_threshold=0.0
                    )
                    print(f"  - Named vector '{vector_name}' 검색 성공: {len(results)}개")
                    break
                except Exception:
                    continue
            else:
                # Unnamed vector로 시도
                try:
                    results = vector_ops.qdrant_client.search(
                        collection_name="email_vectors",
                        query_vector=dummy_vector,
                        limit=3,
                        score_threshold=0.0
                    )
                    print(f"  - Unnamed vector 검색 결과: {len(results)}개")
                except Exception as e:
                    print(f"  - Unnamed vector 검색도 실패: {e}")
                    
    except Exception as e:
        print(f"✗ 샘플 데이터 조회 실패: {e}")
    
    # 6. 실제 임베딩으로 검색 테스트
    print("6. 실제 임베딩으로 검색 테스트...")
    try:
        # 실제 임베딩 생성
        embedding = await vector_ops.create_embedding("테스트 검색어")
        print(f"  - 임베딩 차원: {len(embedding)}")
        
        # 임계값 0.0으로 검색
        results = await vector_ops.search_vectors(
            query_vector=embedding,
            collection="email_vectors",
            score_threshold=0.0,
            limit=5
        )
        print(f"  - 검색 결과 (임계값 0.0): {len(results)}개")
        
        if results:
            for i, result in enumerate(results):
                print(f"    [{i}] ID: {result.id}, Score: {result.score:.4f}")
        else:
            print("  - 여전히 결과 없음")
            
    except Exception as e:
        print(f"✗ 실제 임베딩 검색 실패: {e}")
    
    print("=== Qdrant 디버깅 완료 ===")

if __name__ == "__main__":
    asyncio.run(debug_qdrant())
