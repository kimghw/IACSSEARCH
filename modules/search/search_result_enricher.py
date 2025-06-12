"""Search 결과 보강 서비스

검색 결과에 메타데이터를 추가하고 스니펫을 생성하는 전용 서비스
MongoDB에서 추가 정보를 조회하여 검색 결과를 풍부하게 만듦
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from .repository import SearchRepository
from .schema import EnrichmentData, SearchResult, VectorMatch

logger = structlog.get_logger(__name__)


class SearchResultEnricher:
    """검색 결과 보강 전용 서비스"""
    
    def __init__(self):
        """SearchResultEnricher 초기화"""
        self.repository: Optional[SearchRepository] = None
        self._initialized = False
        
        # 스니펫 설정
        self.snippet_length = 200  # 스니펫 기본 길이
        self.snippet_context = 50  # 매치 주변 컨텍스트 길이
        self.highlight_tag_start = "<mark>"
        self.highlight_tag_end = "</mark>"
        
        # 메타데이터 필드 매핑
        self.metadata_fields = {
            "subject": "제목",
            "sender": "발신자",
            "recipients": "수신자",
            "date": "날짜",
            "attachments": "첨부파일",
            "thread_id": "스레드",
            "tags": "태그"
        }
    
    async def _ensure_initialized(self) -> None:
        """서비스 초기화 확인"""
        if not self._initialized:
            self.repository = SearchRepository()
            self._initialized = True
            logger.info("SearchResultEnricher 초기화 완료")
    
    # === 메인 보강 함수 ===
    
    async def search_result_enrich(
        self,
        vector_matches: List[VectorMatch],
        query_text: Optional[str] = None
    ) -> List[SearchResult]:
        """벡터 매치 결과를 풍부한 검색 결과로 변환
        
        Args:
            vector_matches: 벡터 검색 결과
            query_text: 원본 검색 질의 (스니펫 생성용)
            
        Returns:
            보강된 검색 결과 목록
        """
        await self._ensure_initialized()
        
        if not vector_matches:
            return []
        
        try:
            # 문서 ID 추출
            document_ids = [match.document_id for match in vector_matches]
            
            # 메타데이터 일괄 조회
            metadata_dict = await self.search_result_get_metadata(document_ids)
            
            # 각 매치를 SearchResult로 변환
            enriched_results = []
            for match in vector_matches:
                # 개별 결과 보강
                result = await self.search_result_format_single(
                    match=match,
                    metadata=metadata_dict.get(match.document_id, {}),
                    query_text=query_text
                )
                if result:
                    enriched_results.append(result)
            
            logger.info(
                "결과 보강 완료",
                input_count=len(vector_matches),
                output_count=len(enriched_results),
                metadata_found=len(metadata_dict)
            )
            
            return enriched_results
            
        except Exception as e:
            logger.error("결과 보강 실패", error=str(e))
            # 실패 시 기본 결과 반환
            return self._create_basic_results(vector_matches)
    
    # === 메타데이터 처리 ===
    
    async def search_result_get_metadata(
        self,
        document_ids: List[str]
    ) -> Dict[str, Any]:
        """문서 ID 목록에 대한 메타데이터 조회
        
        Args:
            document_ids: 문서 ID 목록
            
        Returns:
            문서 ID를 키로 하는 메타데이터 딕셔너리
        """
        try:
            # Repository를 통해 MongoDB에서 조회
            metadata_dict = await self.repository.search_repo_get_metadata(document_ids)
            
            logger.debug(
                "메타데이터 조회 완료",
                requested_count=len(document_ids),
                found_count=len(metadata_dict)
            )
            
            return metadata_dict
            
        except Exception as e:
            logger.error("메타데이터 조회 실패", error=str(e))
            return {}
    
    async def search_result_generate_snippet(
        self,
        content: str,
        query: str,
        highlight: bool = True
    ) -> str:
        """검색어 기반 스니펫 생성
        
        Args:
            content: 전체 콘텐츠
            query: 검색어
            highlight: 하이라이팅 여부
            
        Returns:
            생성된 스니펫
        """
        if not content:
            return ""
        
        # 콘텐츠 정리
        cleaned_content = self._clean_content_for_snippet(content)
        
        if not query:
            # 검색어가 없으면 앞부분만 반환
            return cleaned_content[:self.snippet_length] + "..."
        
        # 검색어 위치 찾기
        match_positions = self._find_query_matches(cleaned_content, query)
        
        if not match_positions:
            # 매치가 없으면 앞부분 반환
            return cleaned_content[:self.snippet_length] + "..."
        
        # 가장 관련성 높은 부분 추출
        snippet = self._extract_best_snippet(
            cleaned_content,
            match_positions,
            query
        )
        
        # 하이라이팅 적용
        if highlight:
            snippet = await self._search_result_extract_highlight(snippet, query)
        
        return snippet
    
    # === 결과 포맷팅 ===
    
    async def search_result_format_single(
        self,
        match: VectorMatch,
        metadata: Dict[str, Any],
        query_text: Optional[str] = None
    ) -> Optional[SearchResult]:
        """단일 매치를 SearchResult로 변환
        
        Args:
            match: 벡터 매치 결과
            metadata: 문서 메타데이터
            query_text: 검색 질의
            
        Returns:
            SearchResult 또는 None
        """
        try:
            # 기본 정보 추출
            document_id = match.document_id
            score = match.score
            
            # 메타데이터에서 필드 추출
            title = metadata.get("subject", "제목 없음")
            content = metadata.get("content", "")
            sender = metadata.get("sender", "")
            recipients = metadata.get("recipients", [])
            date = metadata.get("date")
            attachments = metadata.get("attachments", [])
            thread_id = metadata.get("thread_id")
            tags = metadata.get("tags", [])
            
            # 날짜 처리
            if date:
                if isinstance(date, str):
                    try:
                        date = datetime.fromisoformat(date)
                    except:
                        pass
            
            # 스니펫 생성
            snippet = await self.search_result_generate_snippet(
                content=content,
                query=query_text or "",
                highlight=True
            )
            
            # 관련성 점수 계산
            relevance_score = await self._search_result_calculate_relevance(
                match, metadata, query_text
            )
            
            # 보강 데이터 생성
            enrichment_data = EnrichmentData(
                has_attachments=bool(attachments),
                attachment_count=len(attachments),
                attachment_names=[a.get("name", "") for a in attachments] if attachments else [],
                thread_info={
                    "thread_id": thread_id,
                    "position": metadata.get("thread_position", 0)
                } if thread_id else None,
                tags=tags,
                extracted_entities=metadata.get("entities", [])
            )
            
            # SearchResult 생성
            result = SearchResult(
                document_id=document_id,
                title=title,
                snippet=snippet,
                score=score,
                relevance_score=relevance_score,
                metadata={
                    "sender": sender,
                    "recipients": recipients,
                    "date": date.isoformat() if isinstance(date, datetime) else str(date),
                    "content_length": len(content),
                    "has_attachments": bool(attachments)
                },
                enrichment=enrichment_data,
                source_collection=match.collection_name,
                highlight_positions=self._get_highlight_positions(snippet)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "개별 결과 포맷팅 실패",
                document_id=match.document_id,
                error=str(e)
            )
            return None
    
    # === 내부 헬퍼 함수 ===
    
    async def _search_result_calculate_relevance(
        self,
        match: VectorMatch,
        metadata: Dict[str, Any],
        query_text: Optional[str]
    ) -> float:
        """관련성 점수 계산
        
        Args:
            match: 벡터 매치
            metadata: 메타데이터
            query_text: 검색어
            
        Returns:
            관련성 점수 (0.0 ~ 1.0)
        """
        # 기본 점수는 벡터 유사도
        base_score = match.score
        
        # 추가 점수 요소들
        boost_factors = []
        
        # 제목에 검색어 포함 시 부스트
        if query_text and metadata.get("subject"):
            if query_text.lower() in metadata["subject"].lower():
                boost_factors.append(0.2)
        
        # 최근 문서일수록 부스트
        if metadata.get("date"):
            try:
                date = datetime.fromisoformat(metadata["date"])
                days_old = (datetime.now() - date).days
                if days_old < 7:
                    boost_factors.append(0.1)
                elif days_old < 30:
                    boost_factors.append(0.05)
            except:
                pass
        
        # 첨부파일 있으면 약간 부스트
        if metadata.get("attachments"):
            boost_factors.append(0.05)
        
        # 최종 점수 계산 (최대 1.0)
        final_score = min(1.0, base_score + sum(boost_factors))
        
        return final_score
    
    async def _search_result_extract_highlight(
        self,
        text: str,
        query: str
    ) -> str:
        """텍스트에서 검색어 하이라이트
        
        Args:
            text: 원본 텍스트
            query: 검색어
            
        Returns:
            하이라이트된 텍스트
        """
        if not query:
            return text
        
        # 검색어를 단어로 분리
        query_words = query.lower().split()
        
        # 각 단어를 하이라이트
        highlighted = text
        for word in query_words:
            if len(word) < 2:  # 너무 짧은 단어는 스킵
                continue
            
            # 대소문자 구분 없이 매치
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            highlighted = pattern.sub(
                f"{self.highlight_tag_start}\\g<0>{self.highlight_tag_end}",
                highlighted
            )
        
        return highlighted
    
    def _clean_content_for_snippet(self, content: str) -> str:
        """스니펫용 콘텐츠 정리"""
        # HTML 태그 제거
        cleaned = re.sub(r'<[^>]+>', '', content)
        
        # 연속된 공백 제거
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 이메일 인용 제거
        cleaned = re.sub(r'^>+.*$', '', cleaned, flags=re.MULTILINE)
        
        return cleaned.strip()
    
    def _find_query_matches(
        self,
        content: str,
        query: str
    ) -> List[Tuple[int, int]]:
        """콘텐츠에서 검색어 위치 찾기"""
        matches = []
        query_words = query.lower().split()
        content_lower = content.lower()
        
        for word in query_words:
            if len(word) < 2:
                continue
            
            # 모든 매치 위치 찾기
            start = 0
            while True:
                pos = content_lower.find(word, start)
                if pos == -1:
                    break
                matches.append((pos, pos + len(word)))
                start = pos + 1
        
        # 위치순 정렬
        matches.sort(key=lambda x: x[0])
        
        return matches
    
    def _extract_best_snippet(
        self,
        content: str,
        match_positions: List[Tuple[int, int]],
        query: str
    ) -> str:
        """가장 관련성 높은 스니펫 추출"""
        if not match_positions:
            return content[:self.snippet_length] + "..."
        
        # 첫 번째 매치 주변 추출
        first_match_start, first_match_end = match_positions[0]
        
        # 시작 위치 계산
        start = max(0, first_match_start - self.snippet_context)
        end = min(len(content), first_match_end + self.snippet_context + self.snippet_length)
        
        # 단어 경계에서 자르기
        if start > 0:
            # 이전 공백 찾기
            while start > 0 and content[start] != ' ':
                start -= 1
            start = max(0, start)
        
        if end < len(content):
            # 다음 공백 찾기
            while end < len(content) and content[end] != ' ':
                end += 1
        
        snippet = content[start:end].strip()
        
        # 앞뒤 생략 표시
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _get_highlight_positions(self, highlighted_text: str) -> List[Tuple[int, int]]:
        """하이라이트 위치 추출"""
        positions = []
        
        # 하이라이트 태그 위치 찾기
        pattern = re.compile(
            f"{re.escape(self.highlight_tag_start)}(.*?){re.escape(self.highlight_tag_end)}"
        )
        
        # 태그를 제거한 텍스트에서의 실제 위치 계산
        offset = 0
        for match in pattern.finditer(highlighted_text):
            start = match.start() - offset
            # 태그 길이만큼 오프셋 증가
            offset += len(self.highlight_tag_start) + len(self.highlight_tag_end)
            end = start + len(match.group(1))
            positions.append((start, end))
        
        return positions
    
    def _create_basic_results(
        self,
        vector_matches: List[VectorMatch]
    ) -> List[SearchResult]:
        """메타데이터 없이 기본 결과 생성"""
        results = []
        
        for match in vector_matches:
            result = SearchResult(
                document_id=match.document_id,
                title=f"문서 {match.document_id}",
                snippet="메타데이터를 불러올 수 없습니다.",
                score=match.score,
                relevance_score=match.score,
                metadata={},
                enrichment=EnrichmentData(),
                source_collection=match.collection_name
            )
            results.append(result)
        
        return results
