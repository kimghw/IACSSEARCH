# 3. Motor: 집계(Aggregation) 파이프라인

집계 프레임워크는 여러 단계(stage)를 거쳐 문서를 처리하고 계산된 결과를 반환하는 강력한 데이터 처리 도구입니다. 복잡한 데이터 분석 및 리포팅에 필수적입니다.

## 집계 파이프라인 구조
집계 작업은 단계(stage)의 배열로 정의됩니다. 각 단계는 문서를 입력받아 변환한 후 다음 단계로 전달합니다.

```python
pipeline = [
    {"$match": {"status": "active"}},  # 1단계: 'active' 상태인 문서만 필터링
    {"$group": {"_id": "$department", "total_salary": {"$sum": "$salary"}}}, # 2단계: 부서별로 그룹화하여 총 급여 계산
    {"$sort": {"total_salary": -1}} # 3단계: 총 급여가 높은 순으로 정렬
]
```

## 집계 실행
`aggregate()` 메서드를 사용하여 파이프라인을 실행합니다. 이 메서드는 커서를 반환하므로 `async for`로 결과를 처리하는 것이 효율적입니다.

```python
async def get_salary_stats_by_department(collection):
    """부서별 급여 통계를 계산합니다."""
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$department", "average_salary": {"$avg": "$salary"}}},
        {"$sort": {"average_salary": -1}}
    ]
    
    stats = []
    async for result in collection.aggregate(pipeline):
        stats.append(result)
        
    return stats
```

## 주요 집계 단계(Stage)

- **`$match`**: 문서를 필터링합니다. 쿼리 성능을 위해 파이프라인의 가장 앞 단계에 두는 것이 좋습니다.
- **`$group`**: 지정된 ID를 기준으로 문서를 그룹화하고, 각 그룹에 대한 계산(합계, 평균, 최대/최소 등)을 수행합니다.
- **`$sort`**: 결과를 정렬합니다.
- **`$project`**: 출력 문서의 필드를 재구성합니다. 필드를 추가, 제거, 이름 변경할 수 있습니다.
- **`$lookup`**: 다른 컬렉션과 왼쪽 우선 외부 조인(left outer join)을 수행합니다.
- **`$unwind`**: 배열 필드의 각 요소를 별도의 문서로 분리합니다.
- **`$limit`**: 결과 문서 수를 제한합니다.
- **`$skip`**: 지정된 수의 문서를 건너뜁니다.

## `$lookup` (조인) 예제
`users` 컬렉션과 `orders` 컬렉션을 사용자의 `username`을 기준으로 조인하는 예제입니다.

```python
async def get_users_with_orders(users_collection):
    """사용자 정보에 해당 사용자의 주문 목록을 추가합니다."""
    pipeline = [
        {
            "$lookup": {
                "from": "orders",           # 조인할 컬렉션
                "localField": "username",   # 'users' 컬렉션의 조인 키
                "foreignField": "user",     # 'orders' 컬렉션의 조인 키
                "as": "user_orders"         # 조인된 문서가 저장될 필드 이름
            }
        }
    ]
    
    async for user_with_orders in users_collection.aggregate(pipeline):
        print(user_with_orders)
