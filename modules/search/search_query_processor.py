"""Search 질의 처리 서비스

자연어 질의를 처리하여 정규화하고 필터를 추출하는 전용 서비스
질의 검증, 정규화, 자연어 필터 추출 담당
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog

from .schema import DateRange, ProcessedQuery, SearchFilters
from .cache_manager import SearchCacheManager, get_search_cache_manager

logger = structlog.get_logger(__name__)


class SearchQueryProcessor:
    """검색 질의 처리 전용 서비스"""
    
    def __init__(self):
        """SearchQueryProcessor 초기화 - 의존성 없이 생성"""
        self.cache_manager: Optional[SearchCacheManager] = None
        self._initialized = False
        
        # 날짜 관련 패턴
        self.date_patterns = {
            "today": r"오늘|today",
            "yesterday": r"어제|yesterday",
            "this_week": r"이번\s*주|this\s*week",
            "last_week": r"지난\s*주|last\s*week",
            "this_month": r"이번\s*달|this\s*month",
            "last_month": r"지난\s*달|last\s*month",
            "date_range": r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*~\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
            "specific_date": r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
        }
        
        # 발신자/수신자 패턴
        self.person_patterns = {
            "from": r"(?:from:|발신자:|보낸\s*사람:)\s*([^\s,]+)",
            "to": r"(?:to:|수신자:|받는\s*사람:)\s*([^\s,]+)",
            "email": r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
        }
        
        # 키워드 추출 패턴
        self.keyword_patterns = {
            "quoted": r'"([^"]+)"',
            "important": r"중요|important|urgent|긴급",
            "attachment": r"첨부|attachment|attached|파일"
        }
    
    async def set_dependencies(self, **kwargs) -> None:
        """Orchestrator에서 의존성 주입
        
        Args:
            cache_manager: 캐시 관리자 인스턴스
        """
        if 'cache_manager' in kwargs:
            self.cache_manager = kwargs['cache_manager']
            self._initialized = True
            logger.debug("SearchQueryProcessor 의존성 주입 완료")
    
    def _ensure_dependencies(self) -> None:
        """의존성 주입 확인"""
        if not self._initialized or not self.cache_manager:
            raise RuntimeError("SearchQueryProcessor: 의존성이 주입되지 않았습니다. set_dependencies()를 먼저 호출하세요.")
    
    # === 메인 처리 함수 ===
    
    async def search_query_process(
        self,
        query_text: str,
        filters: Optional[SearchFilters] = None
    ) -> ProcessedQuery:
        """검색 질의 처리 메인 함수
        
        Args:
            query_text: 원본 검색 질의
            filters: 사용자가 명시적으로 제공한 필터
            
        Returns:
            ProcessedQuery: 처리된 질의 정보
        """
        self._ensure_dependencies()
        
        try:
            # 캐시 확인
            cached_result = await self.cache_manager.cache_processed_query_get(query_text)
            
            if cached_result:
                logger.debug("처리된 질의 캐시에서 반환", query=query_text[:50])
                return ProcessedQuery(**cached_result)
            
            # 1. 질의 검증
            validation_result = await self.search_query_validate(query_text)
            if not validation_result["valid"]:
                raise ValueError(validation_result["message"])
            
            # 2. 질의 정규화
            normalized_text = await self.search_query_normalize(query_text)
            
            # 3. 자연어에서 필터 추출
            extracted_filters = await self.search_query_extract_filters(query_text)
            
            # 4. 명시적 필터와 추출된 필터 병합
            if filters:
                extracted_filters = self._merge_filters(filters, extracted_filters)
            
            # 5. 언어 감지
            language = await self._search_query_detect_language(normalized_text)
            
            # 6. 키워드 추출
            keywords = await self._search_query_extract_keywords(normalized_text)
            
            # 7. 질의 유형 분류
            query_type = await self._search_query_classify_type(normalized_text, extracted_filters)
            
            # 처리 결과 생성
            processed_query = ProcessedQuery(
                original_text=query_text,
                normalized_text=normalized_text,
                extracted_filters=extracted_filters,
                language=language,
                query_type=query_type,
                keywords=keywords,
                processing_metadata={
                    "processed_at": datetime.now().isoformat(),
                    "has_filters": bool(extracted_filters),
                }
            )
            
            # 캐시 저장
            await self.cache_manager.cache_processed_query_set(
                query_text,
                processed_query.model_dump()
            )
            
            logger.info(
                "질의 처리 완료",
                original_length=len(query_text),
                normalized_length=len(normalized_text),
                filters_extracted=bool(extracted_filters),
                keywords_count=len(keywords)
            )
            
            return processed_query
            
        except Exception as e:
            logger.error("질의 처리 실패", query=query_text[:50], error=str(e))
            # 실패해도 기본 처리 결과 반환
            return ProcessedQuery(
                original_text=query_text,
                normalized_text=query_text.lower().strip(),
                extracted_filters=filters,
                processing_metadata={"error": str(e)}
            )
    
    # === 개별 처리 함수 ===
    
    async def search_query_validate(self, query_text: str) -> Dict[str, Any]:
        """질의 유효성 검증
        
        Args:
            query_text: 검증할 질의
            
        Returns:
            검증 결과 딕셔너리
        """
        # 빈 문자열 체크
        if not query_text or not query_text.strip():
            return {"valid": False, "message": "검색어가 비어있습니다"}
        
        # 길이 체크
        if len(query_text) > 1000:
            return {"valid": False, "message": "검색어가 너무 깁니다 (최대 1000자)"}
        
        # 최소 길이 체크
        if len(query_text.strip()) < 2:
            return {"valid": False, "message": "검색어가 너무 짧습니다 (최소 2자)"}
        
        # 특수문자만으로 구성된 경우 체크
        if re.match(r'^[^a-zA-Z가-힣0-9]+$', query_text):
            return {"valid": False, "message": "유효한 검색어를 입력해주세요"}
        
        return {"valid": True, "message": "OK"}
    
    async def search_query_normalize(self, query_text: str) -> str:
        """질의 정규화
        
        Args:
            query_text: 정규화할 질의
            
        Returns:
            정규화된 질의
        """
        # 공백 정규화
        normalized = ' '.join(query_text.split())
        
        # 특수문자 처리 (따옴표는 유지)
        normalized = re.sub(r'[^\w\s가-힣"\'@.-]', ' ', normalized)
        
        # 중복 공백 제거
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 양끝 공백 제거
        normalized = normalized.strip()
        
        return normalized
    
    async def search_query_extract_filters(self, query_text: str) -> SearchFilters:
        """자연어에서 필터 추출
        
        Args:
            query_text: 필터를 추출할 질의
            
        Returns:
            추출된 필터
        """
        filters = SearchFilters()
        
        # 날짜 필터 추출
        date_range = await self._search_query_parse_date_filters(query_text)
        if date_range:
            filters.date_range = date_range
        
        # 발신자 추출
        sender = self._extract_sender(query_text)
        if sender:
            filters.sender = sender
        
        # 수신자 추출
        recipients = self._extract_recipients(query_text)
        if recipients:
            filters.recipients = recipients
        
        # 첨부파일 여부
        if re.search(self.keyword_patterns["attachment"], query_text, re.IGNORECASE):
            filters.has_attachments = True
        
        # 제목 키워드 추출
        quoted_keywords = re.findall(self.keyword_patterns["quoted"], query_text)
        if quoted_keywords:
            filters.subject_keywords = quoted_keywords
        
        return filters
    
    # === 내부 헬퍼 함수 ===
    
    async def _search_query_clean_text(self, text: str) -> str:
        """텍스트 정리
        
        Args:
            text: 정리할 텍스트
            
        Returns:
            정리된 텍스트
        """
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 이메일 헤더 제거
        text = re.sub(r'^(From|To|Subject|Date):.*$', '', text, flags=re.MULTILINE)
        
        # URL 단순화
        text = re.sub(r'https?://\S+', 'URL', text)
        
        return text.strip()
    
    async def _search_query_detect_language(self, text: str) -> str:
        """언어 감지
        
        Args:
            text: 언어를 감지할 텍스트
            
        Returns:
            감지된 언어 코드
        """
        # 간단한 휴리스틱 기반 언어 감지
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if korean_chars > english_chars:
            return "ko"
        elif english_chars > korean_chars:
            return "en"
        else:
            return "mixed"
    
    async def _search_query_parse_date_filters(self, text: str) -> Optional[DateRange]:
        """날짜 필터 파싱
        
        Args:
            text: 날짜 정보를 추출할 텍스트
            
        Returns:
            DateRange 또는 None
        """
        now = datetime.now()
        
        # 오늘
        if re.search(self.date_patterns["today"], text, re.IGNORECASE):
            return DateRange(
                start_date=now.replace(hour=0, minute=0, second=0, microsecond=0),
                end_date=now.replace(hour=23, minute=59, second=59)
            )
        
        # 어제
        if re.search(self.date_patterns["yesterday"], text, re.IGNORECASE):
            yesterday = now - timedelta(days=1)
            return DateRange(
                start_date=yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
                end_date=yesterday.replace(hour=23, minute=59, second=59)
            )
        
        # 이번 주
        if re.search(self.date_patterns["this_week"], text, re.IGNORECASE):
            start_of_week = now - timedelta(days=now.weekday())
            return DateRange(
                start_date=start_of_week.replace(hour=0, minute=0, second=0, microsecond=0),
                end_date=now
            )
        
        # 날짜 범위
        date_range_match = re.search(self.date_patterns["date_range"], text)
        if date_range_match:
            try:
                start_str, end_str = date_range_match.groups()
                start_date = self._parse_date_string(start_str)
                end_date = self._parse_date_string(end_str)
                if start_date and end_date:
                    return DateRange(start_date=start_date, end_date=end_date)
            except Exception:
                pass
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열 파싱"""
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    def _extract_sender(self, text: str) -> Optional[str]:
        """발신자 추출"""
        # from: 패턴
        from_match = re.search(self.person_patterns["from"], text, re.IGNORECASE)
        if from_match:
            return from_match.group(1)
        
        # 이메일 주소 추출
        email_matches = re.findall(self.person_patterns["email"], text)
        if email_matches:
            return email_matches[0]
        
        return None
    
    def _extract_recipients(self, text: str) -> List[str]:
        """수신자 추출"""
        recipients = []
        
        # to: 패턴
        to_match = re.search(self.person_patterns["to"], text, re.IGNORECASE)
        if to_match:
            recipients.append(to_match.group(1))
        
        return recipients
    
    def _merge_filters(
        self,
        explicit_filters: SearchFilters,
        extracted_filters: SearchFilters
    ) -> SearchFilters:
        """명시적 필터와 추출된 필터 병합"""
        # 명시적 필터를 우선시
        merged = explicit_filters.model_copy()
        
        # 추출된 필터에서 없는 항목만 추가
        if not merged.date_range and extracted_filters.date_range:
            merged.date_range = extracted_filters.date_range
            
        if not merged.sender and extracted_filters.sender:
            merged.sender = extracted_filters.sender
            
        if not merged.recipients and extracted_filters.recipients:
            merged.recipients = extracted_filters.recipients
            
        if merged.has_attachments is None and extracted_filters.has_attachments is not None:
            merged.has_attachments = extracted_filters.has_attachments
            
        return merged
    
    async def _search_query_extract_keywords(self, text: str) -> List[str]:
        """키워드 추출"""
        keywords = []
        
        # 따옴표로 묶인 구문
        quoted = re.findall(self.keyword_patterns["quoted"], text)
        keywords.extend(quoted)
        
        # 중요 키워드
        if re.search(self.keyword_patterns["important"], text, re.IGNORECASE):
            keywords.append("important")
        
        # 2글자 이상의 단어 추출 (명사 추정)
        words = text.split()
        for word in words:
            if len(word) >= 2 and not word.startswith(("@", "http")):
                # 조사 제거 (간단한 휴리스틱)
                cleaned = re.sub(r'[은는이가을를에서의]$', '', word)
                if cleaned and cleaned not in keywords:
                    keywords.append(cleaned)
        
        # 중복 제거 및 최대 10개 제한
        return list(dict.fromkeys(keywords))[:10]
    
    async def _search_query_classify_type(
        self,
        text: str,
        filters: Optional[SearchFilters]
    ) -> str:
        """질의 유형 분류"""
        # 필터가 많으면 상세 검색
        if filters and (filters.date_range or filters.sender or filters.recipients):
            return "filtered_search"
        
        # 따옴표가 있으면 정확한 검색
        if '"' in text:
            return "exact_search"
        
        # 질문 형태
        if text.endswith("?") or "어디" in text or "무엇" in text:
            return "question"
        
        # 기본값
        return "general"
