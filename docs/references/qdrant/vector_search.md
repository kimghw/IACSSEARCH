# Qdrant 벡터 검색 가이드

## 개요
Qdrant Python 클라이언트를 사용한 벡터 검색 구현 방법과 패턴들을 정리합니다.

## 1. 클라이언트 초기화

### 기본 연결
```python
from qdrant_client import QdrantClient

# URL 연결
client = QdrantClient(url="http://localhost:6333")

# 호스트/포트 연결  
client = QdrantClient(host="localhost", port=6333)

# 로컬 메모리 모드 (개발용)
client = QdrantClient(":memory:")

# 로컬 디스크 모드 (개발용)
client = QdrantClient(path="path/to/db")
```

### 비동기 클라이언트
```python
import asyncio
from qdrant_client import AsyncQdrantClient, models

async def main():
    client = AsyncQdrantClient(url="http://localhost:6333")
    
    # 컬렉션 생성
    await client.create_collection(
        collection_name="my_collection",
        vectors_config=models.VectorParams(size=10, distance=models.Distance.COSINE),
    )
    
    # 검색 실행
    res = await client.query_points(
        collection_name="my_collection",
        query=np.random.rand(10).tolist(),
        limit=10,
    )

asyncio.run(main())
```

## 2. 컬렉션 관리

### 컬렉션 생성
```python
from qdrant_client.models import Distance, VectorParams

# 컬렉션 존재 확인 후 생성
if not client.collection_exists("my_collection"):
    client.create_collection(
        collection_name="my_collection",
        vectors_config=VectorParams(size=100, distance=Distance.COSINE),
    )
```

### 벡터 삽입
```python
import numpy as np
from qdrant_client.models import PointStruct

vectors = np.random.rand(100, 100)

# 배치 삽입 (권장)
client.upsert(
    collection_name="my_collection",
    points=[
        PointStruct(
            id=idx,
            vector=vector.tolist(),
            payload={"color": "red", "rand_number": idx % 10}
        )
        for idx, vector in enumerate(vectors)
    ]
)
```

## 3. 벡터 검색

### 기본 벡터 검색
```python
query_vector = np.random.rand(100)

# search 메서드 사용
hits = client.search(
    collection_name="my_collection",
    query_vector=query_vector,
    limit=5
)

# query_points 메서드 사용 (더 새로운 API)
hits = client.query_points(
    collection_name="my_collection",
    query=query_vector,
    limit=5
)
```

### 필터와 함께 검색
```python
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue

# 범위 필터
hits = client.query_points(
    collection_name="my_collection",
    query=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(
                key='rand_number',
                range=Range(gte=3)  # rand_number >= 3
            )
        ]
    ),
    limit=5
)

# 값 매칭 필터
search_result = client.search(
    collection_name="test_collection",
    query_vector=[0.2, 0.1, 0.9, 0.7], 
    query_filter=Filter(
        must=[
            FieldCondition(
                key="city",
                match=MatchValue(value="London")
            )
        ]
    ),
    limit=1
)
```

## 4. 프로젝트에서 사용할 패턴

### 비동기 검색 서비스 구현
```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, Range

class VectorSearchService:
    def __init__(self, url: str):
        self.client = AsyncQdrantClient(url=url)
    
    async def search_vectors(
        self, 
        collection: str, 
        query_vector: List[float],
        filters: Optional[Dict] = None,
        limit: int = 10
    ):
        query_filter = None
        if filters:
            conditions = []
            
            # 날짜 필터
            if 'date_start' in filters:
                conditions.append(
                    FieldCondition(
                        key="date",
                        range=Range(
                            gte=filters['date_start'],
                            lte=filters.get('date_end')
                        )
                    )
                )
            
            # 발신자 필터
            if 'sender' in filters:
                conditions.append(
                    FieldCondition(
                        key="sender",
                        match=MatchValue(value=filters['sender'])
                    )
                )
            
            query_filter = Filter(must=conditions)
        
        return await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        )
```

### 에러 처리 패턴
```python
from qdrant_client.http.exceptions import QdrantException

async def safe_search(client, collection, query_vector, **kwargs):
    try:
        return await client.query_points(
            collection_name=collection,
            query=query_vector,
            **kwargs
        )
    except QdrantException as e:
        logger.error(f"Qdrant 검색 실패: {e}")
        return []
    except Exception as e:
        logger.error(f"예상치 못한 검색 오류: {e}")
        return []
```

## 5. 성능 최적화

### 배치 처리
```python
# 대용량 데이터는 청크로 분할
def chunk_data(data, chunk_size=100):
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

# 배치 삽입
for chunk in chunk_data(vectors, chunk_size=1000):
    client.upsert(collection_name="my_collection", points=chunk)
```

### gRPC 사용 (더 빠른 업로드)
```python
client = QdrantClient(
    host="localhost", 
    grpc_port=6334, 
    prefer_grpc=True
)
```

## 6. 주의사항

1. **페이로드 크기 제한**: 큰 데이터셋은 청크로 분할하여 삽입
2. **비동기 처리**: 프로덕션에서는 AsyncQdrantClient 사용 권장
3. **연결 풀링**: 클라이언트 인스턴스 재사용
4. **에러 처리**: QdrantException 및 네트워크 오류 처리
5. **거리 메트릭**: 임베딩 모델에 적합한 거리 함수 선택 (COSINE, DOT, EUCLIDEAN)

---

**참고**: 이 문서는 Qdrant Client v1.7+ 기준으로 작성되었습니다.
