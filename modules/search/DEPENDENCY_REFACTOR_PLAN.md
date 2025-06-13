# Search 모듈 의존성 구조 개선 작업 계획서

## 📅 작성일: 2025-01-13
## 📌 목적: SearchOrchestrator 레이지 싱글톤 패턴을 통한 의존성 구조 개선

---

## 🔍 현재 상태 분석

### 문제점 요약
1. **인스턴스 중복 생성 문제**
   - 각 서비스가 Repository와 CacheManager를 개별 생성 가능
   - 메모리 낭비 및 상태 불일치 위험

2. **순환 참조 위험**
   - 서비스 간 상호 참조 가능성
   - 의존성 주입 순서 문제

3. **초기화 패턴 불일치**
   - 일부는 생성자, 일부는 지연 초기화
   - 코드 일관성 부족

### 현재 의존성 구조
```
SearchOrchestrator
├── SearchRepository (직접 생성)
├── SearchQueryProcessor (지연 초기화)
├── SearchEmbeddingService (지연 초기화)
├── SearchVectorService (지연 초기화)
├── SearchResultEnricher (지연 초기화)
└── SearchPerformanceMonitor (지연 초기화)

각 서비스별 의존성:
- QueryProcessor → CacheManager
- EmbeddingService → CacheManager
- VectorService → VectorStoreManager
- ResultEnricher → (현재 없음, Repository 필요 예상)
- PerformanceMonitor → CacheManager
```

---

## 🎯 개선 목표

### 핵심 원칙
1. **레이지 싱글톤 패턴**
   - SearchOrchestrator가 공통 의존성 관리
   - 클래스 레벨 싱글톤으로 메모리 효율성 확보

2. **의존성 주입 패턴**
   - 각 서비스는 의존성 없이 생성
   - Orchestrator가 의존성 주입 담당

3. **순환 참조 제거**
   - 단방향 의존성만 허용
   - 서비스 간 직접 참조 금지

---

## 📋 구현 계획

### Phase 1: SearchOrchestrator 리팩토링 (우선순위: 높음)

#### 1.1 클래스 레벨 싱글톤 추가
```python
class SearchOrchestrator:
    # 클래스 레벨 싱글톤 인스턴스
    _repository_instance: Optional[SearchRepository] = None
    _cache_manager_instance: Optional[SearchCacheManager] = None
```

#### 1.2 공통 의존성 초기화 메서드
```python
async def _init_shared_dependencies(self) -> None:
    """공통 의존성 레이지 싱글톤 초기화"""
    if SearchOrchestrator._repository_instance is None:
        SearchOrchestrator._repository_instance = SearchRepository()
        await SearchOrchestrator._repository_instance._ensure_initialized()
    
    if SearchOrchestrator._cache_manager_instance is None:
        SearchOrchestrator._cache_manager_instance = await get_search_cache_manager()
```

#### 1.3 의존성 주입 메서드
```python
async def _inject_dependencies(self) -> None:
    """각 서비스에 의존성 주입"""
    repo = SearchOrchestrator._repository_instance
    cache = SearchOrchestrator._cache_manager_instance
    
    # 각 서비스에 필요한 의존성만 주입
    await self.query_processor.set_dependencies(cache_manager=cache)
    await self.embedding_service.set_dependencies(cache_manager=cache)
    await self.vector_service.set_dependencies(repository=repo)
    await self.result_enricher.set_dependencies(repository=repo)
    await self.performance_monitor.set_dependencies(cache_manager=cache)
```

### Phase 2: 서비스 의존성 주입 패턴 적용

#### 2.1 공통 서비스 패턴
```python
class SearchXXXService:
    def __init__(self):
        # 의존성 없이 생성
        self.repository = None
        self.cache_manager = None
        self._initialized = False
    
    async def set_dependencies(self, **kwargs):
        """Orchestrator에서 의존성 주입"""
        if 'repository' in kwargs:
            self.repository = kwargs['repository']
        if 'cache_manager' in kwargs:
            self.cache_manager = kwargs['cache_manager']
        self._initialized = True
    
    # _ensure_initialized() 메서드 제거
```

#### 2.2 서비스별 수정 사항

**SearchQueryProcessor**
- 변경: `_ensure_initialized()` 제거
- 추가: `set_dependencies(cache_manager)`
- 영향: `search_query_process()` 메서드 수정

**SearchEmbeddingService**
- 변경: `_ensure_initialized()` 제거
- 추가: `set_dependencies(cache_manager)`
- 영향: 모든 public 메서드 수정

**SearchVectorService**
- 변경: `_ensure_initialized()` 제거
- 추가: `set_dependencies(repository)` (필요시)
- 유지: VectorStoreManager는 현재 패턴 유지

**SearchResultEnricher**
- 추가: `set_dependencies(repository)`
- 영향: 데이터 보강 로직에 repository 활용

**SearchPerformanceMonitor**
- 변경: `_ensure_initialized()` 제거
- 추가: `set_dependencies(cache_manager)`

### Phase 3: Repository 정리

#### 3.1 캐시 관련 메서드 정리
- 통합 캐시 관리자 사용 확인
- 중복 캐시 메서드 제거
- 네이밍 컨벤션 통일

#### 3.2 초기화 로직 최적화
- DB 연결 풀 재사용 확인
- 불필요한 초기화 제거

---

## 🔧 구현 순서

### Day 1: 핵심 구조 변경
1. **SearchOrchestrator 수정** (2시간)
   - 싱글톤 인스턴스 변수 추가
   - `_init_shared_dependencies()` 구현
   - `_inject_dependencies()` 구현
   - `_ensure_initialized()` 로직 변경

2. **기본 서비스 2개 수정** (2시간)
   - SearchQueryProcessor
   - SearchEmbeddingService

### Day 2: 나머지 서비스 수정
1. **나머지 서비스 수정** (3시간)
   - SearchVectorService
   - SearchResultEnricher
   - SearchPerformanceMonitor

2. **Repository 정리** (1시간)

### Day 3: 테스트 및 최적화
1. **통합 테스트** (2시간)
2. **성능 측정** (1시간)
3. **문서 업데이트** (1시간)

---

## 📊 예상 효과

### 정량적 개선
| 항목 | Before | After | 개선율 |
|------|--------|-------|--------|
| Repository 인스턴스 | 잠재적 N개 | 1개 | ~75% 감소 |
| CacheManager 인스턴스 | 잠재적 N개 | 1개 | ~75% 감소 |
| 초기화 시간 | O(N) | O(1) | 상수 시간 |
| 메모리 사용량 | 기준 | 25% | 75% 절약 |

### 정성적 개선
- ✅ 순환 참조 완전 제거
- ✅ 코드 일관성 향상
- ✅ 테스트 용이성 증가
- ✅ 유지보수성 향상

---

## ⚠️ 리스크 및 대응 방안

### 리스크 1: API 호환성
- **위험**: 외부 호출 인터페이스 변경
- **대응**: Public 메서드 시그니처 유지

### 리스크 2: 초기화 순서
- **위험**: 의존성 주입 전 서비스 사용
- **대응**: 명확한 에러 메시지 및 검증 로직

### 리스크 3: 성능 저하
- **위험**: 추가 메서드 호출로 인한 오버헤드
- **대응**: 실제로는 초기화가 1회만 발생하므로 개선됨

---

## 📝 체크리스트

### 구현 전
- [ ] 현재 코드 백업
- [ ] 테스트 시나리오 준비
- [ ] 성능 측정 기준 설정

### 구현 중
- [ ] SearchOrchestrator 싱글톤 구현
- [ ] 의존성 주입 메서드 구현
- [ ] 각 서비스 set_dependencies 추가
- [ ] _ensure_initialized 제거
- [ ] Repository 캐시 메서드 정리

### 구현 후
- [ ] 단위 테스트 실행
- [ ] 통합 테스트 실행
- [ ] 성능 측정 비교
- [ ] 문서 업데이트
- [ ] README.md 수정

---

## 🔄 롤백 계획

만약 문제 발생 시:
1. Git revert로 이전 버전 복구
2. 서비스별 점진적 롤백 가능
3. Feature flag로 신/구 버전 전환 고려

---

## 📚 참고 사항

### 관련 패턴
- Lazy Singleton Pattern
- Dependency Injection Pattern
- Service Locator Anti-pattern (피해야 함)

### 주의사항
- 프로젝트 아키텍처 규칙 준수
- 350줄 제한 준수 (필요시 파일 분할)
- 네이밍 컨벤션 유지 (search_ prefix)

---

**작성자**: Cline AI Assistant  
**검토 필요**: 프로젝트 리드 개발자
