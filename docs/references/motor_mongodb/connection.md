# 1. Motor: MongoDB 연결

## 핵심 원칙: 단일 클라이언트 인스턴스
성능 최적화를 위해 **애플리케이션 수명 주기 동안 `AsyncIOMotorClient` 인스턴스를 하나만 생성하고 전체에서 재사용**하는 것이 매우 중요합니다. Motor는 내부적으로 커넥션 풀을 관리하므로, 요청마다 클라이언트를 생성하면 심각한 성능 저하가 발생합니다.

## 연결 설정 예제
일반적으로 `database.py` 또는 설정 파일에서 클라이언트를 초기화하고 필요한 곳에 주입하여 사용합니다.

```python
# /infra/database.py
import motor.motor_asyncio
from app.core.config import settings # .env 파일에서 설정 로드

# 애플리케이션 전체에서 공유될 클라이언트 인스턴스
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)

# 데이터베이스 참조
db = client.get_database(settings.MONGODB_DB_NAME)

def get_database():
    """데이터베이스 객체를 반환하는 의존성 주입용 함수"""
    return db

def get_collection(name: str):
    """컬렉션 객체를 반환하는 헬퍼 함수"""
    return db.get_collection(name)

# 연결 종료 (애플리케이션 종료 시 호출)
def close_mongo_connection():
    client.close()
```

### 연결 문자열 (Connection String)
`.env` 파일에 연결 정보를 저장하고 관리합니다.

```env
# .env
MONGODB_URL="mongodb://user:password@localhost:27017/"
MONGODB_DB_NAME="my_app_db"
```

## 연결 확인
애플리케이션 시작 시 `server_info()`를 호출하여 MongoDB 서버와의 연결을 확인할 수 있습니다.

```python
import pymongo.errors

async def check_connection():
    try:
        await client.server_info()
        print("✅ MongoDB에 성공적으로 연결되었습니다.")
    except pymongo.errors.ConnectionFailure as e:
        print(f"❌ MongoDB 연결 실패: {e}")
        # 연결 실패 시 애플리케이션을 종료하거나 재시도 로직 추가
