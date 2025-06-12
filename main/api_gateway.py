"""API 게이트웨이

FastAPI를 사용한 REST API 엔드포인트 정의
모든 모듈의 API 엔드포인트를 통합 관리
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from modules.search import SearchOrchestrator, SearchQuery, SearchResponse

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명 주기 관리"""
    # 시작 시
    logger.info("API Gateway 시작")
    yield
    # 종료 시
    logger.info("API Gateway 종료")


# FastAPI 앱 생성
app = FastAPI(
    title="IACS Search API",
    description="지능형 첨부파일 분류 시스템 검색 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 구체적인 도메인 지정
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 오케스트레이터 인스턴스
search_orchestrator = SearchOrchestrator()


# === 예외 처리 핸들러 ===

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """ValueError 처리"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Invalid request",
            "detail": str(exc),
            "type": "ValueError"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 처리"""
    logger.error("처리되지 않은 예외", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }
    )


# === 루트 엔드포인트 ===

@app.get("/")
async def root():
    """API 루트 정보"""
    return {
        "service": "IACS Search API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "search": "/api/v1/search",
            "vector_search": "/api/v1/search/vector",
            "collections": "/api/v1/search/collections",
            "health": "/api/v1/search/health"
        }
    }


# === Search 모듈 엔드포인트 ===

@app.post("/api/v1/search", response_model=SearchResponse, summary="검색 실행")
async def search_endpoint(request: SearchQuery) -> SearchResponse:
    """일반 검색 엔드포인트
    
    자연어 질의를 처리하여 관련 문서를 검색합니다.
    필터 추출, 임베딩 생성, 벡터 검색, 결과 보강을 자동으로 수행합니다.
    
    Args:
        request: 검색 요청 정보
        
    Returns:
        검색 결과 응답
    """
    try:
        logger.info(
            "검색 요청 수신",
            query=request.query_text[:50],
            mode=request.search_mode.value
        )
        
        response = await search_orchestrator.search_orchestrator_process(request)
        
        logger.info(
            "검색 응답 전송",
            query_id=response.query_id,
            result_count=response.total_count,
            time_ms=response.search_time_ms
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("검색 처리 실패", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="검색 처리 중 오류가 발생했습니다"
        )


@app.post("/api/v1/search/vector", response_model=SearchResponse, summary="순수 벡터 검색")
async def vector_only_search(
    query_text: str,
    limit: Optional[int] = 20,
    score_threshold: Optional[float] = 0.7,
    collections: Optional[List[str]] = None
) -> SearchResponse:
    """순수 벡터 검색 전용 엔드포인트
    
    필터 없이 의미적 유사도만으로 검색합니다.
    탐색적 검색이나 관련 문서 찾기에 유용합니다.
    
    Args:
        query_text: 검색할 텍스트
        limit: 결과 개수 제한 (기본값: 20)
        score_threshold: 유사도 점수 임계값 (기본값: 0.7)
        collections: 검색할 컬렉션 목록
        
    Returns:
        검색 결과 응답
    """
    try:
        # SearchQuery 객체 생성 (순수 벡터 검색 모드)
        request = SearchQuery(
            query_text=query_text,
            search_mode="vector_only",
            limit=limit,
            score_threshold=score_threshold,
            target_collections=collections,
            auto_extract_filters=False  # 필터 추출 비활성화
        )
        
        response = await search_orchestrator.search_orchestrator_process(request)
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("벡터 검색 처리 실패", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벡터 검색 처리 중 오류가 발생했습니다"
        )


@app.get("/api/v1/search/collections", summary="사용 가능한 컬렉션 목록")
async def get_available_collections() -> List[str]:
    """사용 가능한 컬렉션 목록 조회
    
    검색 가능한 모든 벡터 컬렉션 목록을 반환합니다.
    
    Returns:
        컬렉션 이름 목록
    """
    try:
        # SearchVectorService를 직접 사용
        from modules.search.search_vector_service import SearchVectorService
        
        vector_service = SearchVectorService()
        collections = await vector_service.search_vector_get_available_collections()
        
        return collections
        
    except Exception as e:
        logger.error("컬렉션 목록 조회 실패", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="컬렉션 목록 조회 중 오류가 발생했습니다"
        )


@app.get("/api/v1/search/health", summary="서비스 헬스체크")
async def search_health_check():
    """검색 서비스 헬스체크
    
    서비스와 관련 구성요소들의 상태를 확인합니다.
    
    Returns:
        헬스 상태 정보
    """
    try:
        health_status = await search_orchestrator.search_orchestrator_health_check()
        
        # 상태에 따른 HTTP 코드 결정
        if health_status.status == "healthy":
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content=health_status.model_dump()
        )
        
    except Exception as e:
        logger.error("헬스체크 실패", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "search",
                "error": str(e)
            }
        )


@app.get("/api/v1/search/performance", summary="성능 메트릭스 조회")
async def get_performance_metrics():
    """검색 서비스 성능 메트릭스 조회
    
    현재까지의 성능 통계와 메트릭스를 반환합니다.
    
    Returns:
        성능 메트릭스 정보
    """
    try:
        metrics = await search_orchestrator.search_orchestrator_get_performance_metrics()
        
        return {
            "status": "success",
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error("성능 메트릭스 조회 실패", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="성능 메트릭스 조회 중 오류가 발생했습니다"
        )


@app.get("/api/v1/search/optimization", summary="성능 최적화 제안")
async def get_optimization_suggestions():
    """검색 서비스 성능 최적화 제안
    
    현재 성능 분석을 기반으로 최적화 제안을 반환합니다.
    
    Returns:
        최적화 제안 정보
    """
    try:
        suggestions = await search_orchestrator.search_orchestrator_get_optimization_suggestions()
        
        return {
            "status": "success",
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error("최적화 제안 조회 실패", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="최적화 제안 조회 중 오류가 발생했습니다"
        )


# === 공통 엔드포인트 ===

@app.get("/health", summary="전체 서비스 헬스체크")
async def general_health_check():
    """전체 API 서비스 헬스체크
    
    Returns:
        서비스 상태 정보
    """
    return {
        "status": "healthy",
        "service": "api_gateway",
        "version": "1.0.0",
        "modules": {
            "search": "active"
        }
    }


# === 개발용 엔드포인트 (프로덕션에서는 제거) ===

if __name__ == "__main__":
    import uvicorn
    
    # 개발 서버 실행
    uvicorn.run(
        "main.api_gateway:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
