# 프로젝트 참고 문서

이 폴더는 프로젝트에서 사용하는 외부 라이브러리들의 참고 문서를 저장합니다.

## 📂 문서 구조

### 🔍 검색 모듈 관련
- **qdrant/**: Qdrant 벡터 데이터베이스 클라이언트 사용법
- **motor_mongodb/**: Motor (비동기 MongoDB) 클라이언트 사용법  
- **redis/**: Redis (aioredis) 비동기 클라이언트 사용법

### 🌐 웹 프레임워크
- **fastapi/**: FastAPI 웹 프레임워크 사용법
- **pydantic/**: Pydantic 데이터 검증 라이브러리 사용법

## 📖 사용법

각 폴더의 문서들은 실제 프로젝트에서 사용하는 패턴을 중심으로 정리되어 있습니다.

### 검색 모듈 개발 시 참고
```
docs/references/qdrant/vector_search.md  # 벡터 검색 구현
docs/references/motor_mongodb/async_operations.md  # 비동기 DB 작업
docs/references/redis/caching_patterns.md  # 캐싱 전략
```

### API 개발 시 참고
```
docs/references/fastapi/async_endpoints.md  # 비동기 엔드포인트
docs/references/pydantic/model_validation.md  # 데이터 모델 검증
```

## 🔄 업데이트 정책

- 새로운 라이브러리 사용 시 해당 폴더와 문서 추가
- 사용 패턴 변경 시 관련 문서 업데이트
- 프로젝트 아키텍처 변경 시 참고 문서 재정리

---

**마지막 업데이트**: 2025-01-13
**관리자**: 프로젝트 개발팀
