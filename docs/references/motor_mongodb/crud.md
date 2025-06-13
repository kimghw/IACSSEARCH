# 2. Motor: 기본 CRUD 작업

모든 데이터베이스 작업은 비동기(`async`/`await`)로 이루어집니다.

## Create (생성)

### `insert_one`: 단일 문서 삽입
```python
async def create_user(collection, user_data: dict):
    """단일 사용자를 데이터베이스에 추가합니다."""
    result = await collection.insert_one(user_data)
    print(f"사용자 추가 완료, ID: {result.inserted_id}")
    return result.inserted_id
```

### `insert_many`: 여러 문서 동시 삽입 (성능 우수)
```python
async def create_multiple_users(collection, users_data: list[dict]):
    """여러 사용자를 한 번의 요청으로 추가합니다."""
    result = await collection.insert_many(users_data)
    print(f"{len(result.inserted_ids)}명의 사용자 추가 완료.")
    return result.inserted_ids
```

## Read (읽기)

### `find_one`: 조건에 맞는 첫 번째 문서 조회
```python
from bson import ObjectId

async def get_user_by_id(collection, user_id: str):
    """ID로 특정 사용자를 조회합니다."""
    user = await collection.find_one({"_id": ObjectId(user_id)})
    return user
```

### `find`: 조건에 맞는 모든 문서 조회 (커서 사용)
`find`는 커서(cursor)를 반환하며, `async for` 루프를 통해 효율적으로 처리할 수 있습니다.

```python
async def get_active_users(collection):
    """활성 상태인 모든 사용자를 조회합니다."""
    users = []
    cursor = collection.find({"status": "active"}).sort("username", 1)
    async for user in cursor:
        users.append(user)
    return users
```
**팁**: 대용량 데이터를 한 번에 메모리에 올리는 `await cursor.to_list(length=None)`은 메모리 부족을 유발할 수 있으므로 주의해야 합니다.

## Update (수정)

### `update_one`: 조건에 맞는 첫 번째 문서 수정
```python
async def update_user_email(collection, user_id: str, new_email: str):
    """사용자의 이메일 주소를 업데이트합니다."""
    result = await collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"email": new_email}}
    )
    return result.modified_count > 0
```

### `update_many`: 조건에 맞는 모든 문서 수정
```python
async def deactivate_all_users(collection):
    """모든 사용자를 비활성 상태로 변경합니다."""
    result = await collection.update_many({}, {"$set": {"status": "inactive"}})
    return result.modified_count
```

## Delete (삭제)

### `delete_one`: 조건에 맞는 첫 번째 문서 삭제
```python
async def delete_user(collection, user_id: str):
    """특정 사용자를 삭제합니다."""
    result = await collection.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0
```

### `delete_many`: 조건에 맞는 모든 문서 삭제
```python
async def delete_inactive_users(collection):
    """비활성 상태인 모든 사용자를 삭제합니다."""
    result = await collection.delete_many({"status": "inactive"})
    return result.deleted_count
