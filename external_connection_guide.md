# IACSRAG 프로젝트 외부 접속 가이드

## 개요
IACSRAG 프로젝트에서 사용하는 MongoDB, Qdrant, Kafka 서버의 접속 정보와 데이터 타입 정보를 정리한 문서입니다.

## 1. 서버 접속 정보

### 1.1 MongoDB
```yaml
접속 정보:
  호스트: localhost
  포트: 27017
  데이터베이스: iacsrag_dev
  사용자명: admin
  비밀번호: password
  연결 URL: mongodb://admin:password@localhost:27017

연결 풀 설정:
  최소 풀 크기: 10
  최대 풀 크기: 100
  
Docker 컨테이너:
  이미지: mongo:7.0
  컨테이너명: iacsrag-mongodb
  볼륨: mongodb_data:/data/db
```

### 1.2 Qdrant (벡터 데이터베이스)
```yaml
접속 정보:
  호스트: localhost
  HTTP 포트: 6333
  gRPC 포트: 6334
  API 키: (없음 - 개발환경)
  연결 URL: http://localhost:6333

컬렉션 설정:
  기본 컬렉션명: documents
  벡터 차원: 1536 (OpenAI text-embedding-3-small)
  
Docker 컨테이너:
  이미지: qdrant/qdrant:v1.7.0
  컨테이너명: iacsrag-qdrant
  볼륨: qdrant_data:/qdrant/storage
```

### 1.3 Kafka
```yaml
접속 정보:
  브로커: localhost:9092
  Zookeeper: localhost:2181
  
Docker 컨테이너:
  Kafka 이미지: confluentinc/cp-kafka:7.4.0
  Kafka 컨테이너명: iacsrag-kafka
  Zookeeper 이미지: confluentinc/cp-zookeeper:7.4.0
  Zookeeper 컨테이너명: iacsrag-zookeeper

관리 UI:
  Kafka UI: http://localhost:8080
  컨테이너명: iacsrag-kafka-ui
```

### 1.4 Redis (선택사항)
```yaml
접속 정보:
  호스트: localhost
  포트: 6379
  연결 URL: redis://localhost:6379
  
Docker 컨테이너:
  이미지: redis:7.2-alpine
  컨테이너명: iacsrag-redis
```

## 2. MongoDB 데이터 구조

### 2.1 컬렉션 목록
```yaml
주요 컬렉션:
  - documents: 문서 정보
  - users: 사용자 정보
  - processing_jobs: 처리 작업
  - text_chunks: 텍스트 청크
  - search_queries: 검색 쿼리
  - search_results: 검색 결과
  - system_metrics: 시스템 메트릭
  - alerts: 알림 정보
```

### 2.6 Mail Raw Data MongoDB 스키마



## 3. Qdrant 데이터 구조

### 3.1 컬렉션 설정
```yaml
컬렉션명: documents
벡터 설정:
  차원: 1536
  거리 메트릭: Cosine
  인덱스 타입: HNSW
  
포인트 구조:
  id: UUID (문자열)
  vector: [1536개 float 값]
  payload: 메타데이터 객체
```

### 3.2 Mail Raw Data 다중 벡터 포인트 구조

{
  "id": "vector-uuid",
  "vectors": {
    "subject": [0.1, 0.2, ...],  // 제목 임베딩 벡터
    "body": [0.4, 0.5, ...]      // 본문 임베딩 벡터
  },
  "payload": {
    "document_id": "mongodb-document-id",
    "subjectprefix": "EA004",
    "subject": "[EA004] 이메일 제목",
    "body": "플레인 텍스트 본문",
    "sender_name": "발신자 이름",
    "sender_address": "sender@example.com",
    "recipients": {...},
    "has_attachments": false,
    "receivedDate": "2024-01-01T00:00:00Z"
  }
}



## 4. Kafka 토픽 및 이벤트 구조

### 4.1 주요 토픽 목록
```yaml
문서 관련:
  - document-uploaded (파티션: 3)
  - document-processed (파티션: 3)

이메일 관련:
  - email-graph-iacs-events (파티션: 5)
  - email-processing-events (파티션: 3)
  - email-raw-data-events (파티션: 3)

처리 작업 관련:
  - processing-job-events (파티션: 3)
  - text-extraction-events (파티션: 3)
  - chunking-events (파티션: 3)
  - embedding-events (파티션: 3)

검색 관련:
  - search-query-events (파티션: 3)
  - search-result-events (파티션: 3)

모니터링 관련:
  - system-metrics (파티션: 1)
  - system-alerts (파티션: 1)
  - health-check (파티션: 1)
```

### 4.2 표준 이벤트 구조
```json
{
  "event_type": "string",
  "source": "iacsrag",
  "correlation_id": "UUID string",
  "timestamp": "ISO 8601 timestamp",
  "version": "string",
  "data": {
    // 이벤트별 데이터
  }
}


### 4.5 Mail Raw Data 이벤트 구조
```json
{
  "event_type": "email.raw_data_received",
  "event_id": "unique-event-id",
  "account_id": "user-account-id",
  "occurred_at": "2024-01-01T00:00:00Z",
  "api_endpoint": "/v1.0/me/messages",
  "response_status": 200,
  "request_params": {
    "$select": "id,subject,from,body,toRecipients,ccRecipients,bccRecipients,hasAttachments,receivedDateTime,importance,isRead,bodyPreview,categories,flag",
    "$top": 50,
    "$skip": 0
  },
  "response_data": {
    "value": [
      {
        "id": "graph-email-id",
        "subject": "[EA004] 이메일 제목",
        "from": {
          "emailAddress": {
            "name": "발신자 이름",
            "address": "sender@example.com"
          }
        },
        "body": {
          "contentType": "html",
          "content": "<html><body>이메일 본문 HTML</body></html>"
        },
        "toRecipients": [
          {
            "emailAddress": {
              "name": "수신자 이름",
              "address": "recipient@example.com"
            }
          }
        ],
        "ccRecipients": [],
        "bccRecipients": [],
        "hasAttachments": false,
        "receivedDateTime": "2024-01-01T00:00:00Z",
        "importance": "normal",
        "isRead": false,
        "bodyPreview": "이메일 미리보기 텍스트",
        "categories": [],
        "flag": {
          "flagStatus": "notFlagged"
        }
      }
    ],
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages",
    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=50"
  },
  "response_timestamp": "2024-01-01T00:00:00Z"
}
```

## 5. 컨슈머 그룹 정보

### 5.1 주요 컨슈머 그룹
```yaml
document-processing-group:
  토픽: [document-uploaded, processing-job-events]
  컨슈머 수: 3
  처리 방식: 병렬

email-processing-group:
  토픽: [email-graph-iacs-events, email-processing-events]
  컨슈머 수: 2
  처리 방식: 순차

search-analytics-group:
  토픽: [search-query-events, search-result-events]
  컨슈머 수: 1
  처리 방식: 배치

monitoring-group:
  토픽: [system-metrics, system-alerts, health-check]
  컨슈머 수: 1
  처리 방식: 실시간
```

## 6. 연결 예시 코드

### 6.1 MongoDB 연결 (Python)
```python
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

# 동기 연결
client = MongoClient("mongodb://admin:password@localhost:27017")
db = client.iacsrag_dev

# 비동기 연결
async_client = AsyncIOMotorClient("mongodb://admin:password@localhost:27017")
async_db = async_client.iacsrag_dev
```

### 6.2 Qdrant 연결 (Python)
```python
from qdrant_client import QdrantClient
from qdrant_client.http import models

# 클라이언트 생성
client = QdrantClient(host="localhost", port=6333)

# 컬렉션 정보 조회
collection_info = client.get_collection("documents")

# 검색 예시
search_result = client.search(
    collection_name="documents",
    query_vector=[0.1, 0.2, ...],  # 1536차원 벡터
    limit=10
)
```

### 6.3 Kafka 연결 (Python)
```python
from kafka import KafkaProducer, KafkaConsumer
import json

# Producer
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

# Consumer
consumer = KafkaConsumer(
    'document-uploaded',
    bootstrap_servers=['localhost:9092'],
    group_id='my-consumer-group',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
```

## 7. 환경 설정 파일

### 7.1 .env.development 주요 설정
```bash
# MongoDB
MONGODB_URL=mongodb://admin:password@localhost:27017
MONGODB_DATABASE=iacsrag_dev

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=documents

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP_ID=iacsrag-dev

# Redis
REDIS_URL=redis://localhost:6379
```

### 7.2 Docker Compose 실행
```bash
# 모든 서비스 시작
docker-compose up -d

# 특정 서비스만 시작
docker-compose up -d mongodb qdrant kafka

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f kafka
```

## 8. 주의사항

### 8.1 보안
- 개발 환경용 설정이므로 프로덕션에서는 보안 설정 필요
- MongoDB, Kafka 등에 인증 및 암호화 적용 권장
- 네트워크 접근 제어 설정 필요

### 8.2 성능
- MongoDB 인덱스 최적화 필요
- Qdrant 컬렉션 설정 튜닝 권장
- Kafka 파티션 수 조정 고려

### 8.3 모니터링
- 각 서비스별 헬스체크 구현
- 메트릭 수집 및 알림 설정
- 로그 중앙화 관리 권장

이 문서는 IACSRAG 프로젝트의 외부 시스템 연동을 위한 기본 가이드입니다. 실제 운영 환경에서는 보안, 성능, 가용성을 고려한 추가 설정이 필요합니다.
