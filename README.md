# IACS Search System

IACS(Intelligent Automated Content Search) 시스템은 다양한 데이터 소스에서 지능형 검색을 제공하는 시스템입니다.

## 주요 기능

- 하이브리드 검색 (키워드 + 벡터 검색)
- 다중 컬렉션 검색
- 실시간 성능 모니터링
- 캐시 기반 성능 최적화

## 시스템 구성

- **Search Module**: 검색 오케스트레이터 및 관련 서비스
- **Infrastructure**: 데이터베이스, 캐시, 벡터 스토어 연결
- **API Gateway**: FastAPI 기반 REST API

## 설치 및 실행

```bash
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env

# 서비스 실행
uv run python main/api_gateway.py
```

## 테스트

```bash
# 개별 함수 테스트
uv run python tests/test_orchestrator_functions.py

# 통합 검색 테스트
uv run python tests/test_search_orchestrator.py
