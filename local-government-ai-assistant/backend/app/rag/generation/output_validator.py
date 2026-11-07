"""
Output validation to prevent LLM hallucination.

Validation strategies:
1. Length checks (too short = incomplete, too long = verbose)
2. Language verification (must be Vietnamese)
3. Evidence checking (answer must use context)
4. Confidence filtering (no uncertain language)

Based on research:
- "Preventing Hallucinations in RAG Systems" (2024)
- Evidence-based validation reduces hallucination by 60%
"""

from typing import List, Optional, Tuple, Set
import re
import unicodedata

from app.models.data_models import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """
    Validate LLM-generated answers for quality and truthfulness.
    
    Checks:
    1. Structural validity (length, format)
    2. Language compliance (Vietnamese)
    3. Evidence grounding (uses provided context)
    4. Legal citation present and grounded in retrieved metadata
    5. No internal IDs/file references in the user-facing answer
    6. Confidence level (no uncertain phrases)
    """
    
    INTERNAL_REFERENCE_RE = re.compile(
        r"(?:\bdocument_id\b|\ban_phu_\d+\b|\bchunk\s*\d+\b|"
        r"\bTài\s+liệu\s+\d+\b|\.pdf\b|\.txt\b)",
        re.IGNORECASE,
    )

    # Citation contract is số hiệu/ngày/cơ quan only — a URL in the answer
    # (Phase 8) means the model leaked a source link instead of that form.
    URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
    
    # Honest "no information found" answer: it claims nothing, so demanding a
    # legal citation would reject it even though it is the correct reply when
    # the corpus has no matching document.
    NO_INFO_RE = re.compile(
        r"(không\s+tìm\s+thấy\s+(?:thông\s+tin|tài\s+liệu|dữ\s+liệu)"
        r"|không\s+có\s+(?:thông\s+tin|tài\s+liệu|dữ\s+liệu)"
        r"|chưa\s+(?:tìm\s+thấy|có)\s+(?:thông\s+tin|tài\s+liệu))",
        re.IGNORECASE,
    )
    
    MIN_ANSWER_LENGTH = 20      # Minimum chars for complete answer
    MAX_ANSWER_LENGTH = 2500    # Maximum chars; list answers in legal docs run long
    
    # Forbidden uncertain phrases that indicate hallucination risk
    FORBIDDEN_PHRASES = [
        "tôi không chắc chắn",
        "có lẽ",
        "dường như",
        "theo ý kiến của tôi",
        "tôi nghĩ rằng",
        "tôi cho rằng",
        "nếu tôi không nhầm",
    ]
    
    # Required Vietnamese diacritics (at least some must appear)
    VIETNAMESE_CHARS = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    
    def __init__(
        self,
        min_evidence_ratio: float = 0.4,
        strict_mode: bool = False
    ):
        """
        Initialize validator.
        
        Args:
            min_evidence_ratio: Minimum ratio of answer words that must
                                appear in context (0-1)
            strict_mode: If True, apply stricter validation rules
        """
        self.min_evidence_ratio = min_evidence_ratio
        self.strict_mode = strict_mode
        
        logger.info(
            "OutputValidator initialized",
            extra={
                "min_evidence_ratio": min_evidence_ratio,
                "strict_mode": strict_mode
            }
        )
    
    def validate(
        self,
        answer: str,
        query: str,
        context_chunks: List[RetrievedChunk]
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive answer validation.
        
        Args:
            answer: Generated answer from LLM
            query: Original user query
            context_chunks: Context chunks provided to LLM
            
        Returns:
            (is_valid, error_message)
            - (True, None) if valid
            - (False, error_description) if invalid
        """
        # Check 1: Structural validity
        valid, error = self._check_structure(answer)
        if not valid:
            return False, f"Structure check failed: {error}"
        
        # Check 2: Vietnamese language
        valid, error = self._check_vietnamese(answer)
        if not valid:
            return False, f"Language check failed: {error}"
        
        # Check 3: Evidence grounding (most important)
        valid, error = self._check_evidence(answer, context_chunks)
        if not valid:
            return False, f"Evidence check failed: {error}"
        
        # Check 4: Legal citation must come from retrieved metadata
        valid, error = self._check_citation(answer, context_chunks)
        if not valid:
            return False, f"Citation check failed: {error}"

        # Check 5: Confidence level
        valid, error = self._check_confidence(answer)
        if not valid:
            return False, f"Confidence check failed: {error}"
        
        logger.debug("Answer passed all validation checks")
        return True, None

    def validate_direct(
        self,
        answer: str,
        query: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an answer produced WITHOUT retrieved context
        (direct LLM fallback when retrieval returned nothing).

        Evidence overlap and legal citation cannot apply — there are no chunks —
        so only the checks that still hold are run: structure, Vietnamese,
        no internal IDs, no uncertain language.
        """
        valid, error = self._check_structure(answer)
        if not valid:
            return False, f"Structure check failed: {error}"

        valid, error = self._check_vietnamese(answer)
        if not valid:
            return False, f"Language check failed: {error}"

        internal = self.INTERNAL_REFERENCE_RE.search(answer)
        if internal:
            return False, f"Internal reference check failed: {internal.group(0)}"

        url = self.URL_RE.search(answer)
        if url:
            return False, f"URL check failed: {url.group(0)}"

        valid, error = self._check_confidence(answer)
        if not valid:
            return False, f"Confidence check failed: {error}"

        logger.debug("Direct answer passed validation checks")
        return True, None
    
    def _check_structure(self, answer: str) -> Tuple[bool, Optional[str]]:
        """
        Check answer structural validity.
        
        Validates:
        - Not empty
        - Length within bounds
        - Contains actual content (not just whitespace)
        """
        if not answer or not answer.strip():
            return False, "Answer is empty"
        
        answer_length = len(answer.strip())
        
        if answer_length < self.MIN_ANSWER_LENGTH:
            return False, f"Answer too short ({answer_length} < {self.MIN_ANSWER_LENGTH})"
        
        if answer_length > self.MAX_ANSWER_LENGTH:
            return False, f"Answer too long ({answer_length} > {self.MAX_ANSWER_LENGTH})"
        
        return True, None
    
    def _check_vietnamese(self, answer: str) -> Tuple[bool, Optional[str]]:
        """
        Check answer is in Vietnamese.
        
        Method: Verify presence of Vietnamese diacritics
        """
        answer_lower = answer.lower()
        
        # Count Vietnamese characters
        viet_char_count = sum(
            1 for char in answer_lower
            if char in self.VIETNAMESE_CHARS
        )
        
        # Must have at least some Vietnamese characters
        # (at least 1% of total length)
        min_viet_chars = max(5, len(answer) * 0.01)
        
        if viet_char_count < min_viet_chars:
            return False, f"Insufficient Vietnamese characters ({viet_char_count} < {min_viet_chars})"
        
        return True, None
    
    def _check_evidence(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check answer is grounded in provided evidence.
        
        Method: Extract key terms from answer and verify they
                appear in the context chunks.
        
        This is the most important check for preventing hallucination.
        """
        if not chunks:
            return False, "No context chunks provided"
        
        # Combine all context. Citation metadata is trusted context too; the
        # answer is required to repeat it, so excluding it would penalize a
        # perfectly grounded legal answer.
        context_parts = [chunk.text for chunk in chunks]
        for chunk in chunks:
            metadata = chunk.metadata or {}
            context_parts.extend(
                str(metadata.get(key) or "")
                for key in ("citation", "citation_label", "doc_number")
            )
        context_text = " ".join(context_parts).lower()
        
        # Extract answer terms (words 3+ characters)
        answer_lower = answer.lower()
        answer_terms = self._extract_terms(answer_lower)
        
        if not answer_terms:
            return False, "Could not extract terms from answer"
        
        # Count terms that appear in context
        verified_terms = sum(
            1 for term in answer_terms
            if term in context_text
        )
        
        # Calculate overlap ratio
        overlap_ratio = verified_terms / len(answer_terms)
        
        logger.debug(
            "Evidence check",
            extra={
                "answer_terms": len(answer_terms),
                "verified_terms": verified_terms,
                "overlap_ratio": overlap_ratio,
                "threshold": self.min_evidence_ratio
            }
        )
        
        # Must meet minimum evidence ratio
        if overlap_ratio < self.min_evidence_ratio:
            return False, (
                f"Insufficient evidence overlap "
                f"({overlap_ratio:.2f} < {self.min_evidence_ratio}). "
                f"Answer may contain hallucination."
            )
        
        return True, None
    
    @staticmethod
    def _normalize_citation_text(text: str) -> str:
        text = unicodedata.normalize("NFC", text or "").lower()
        return re.sub(r"\s+", "", text)

    def _check_citation(
        self,
        answer: str,
        chunks: List[RetrievedChunk],
    ) -> Tuple[bool, Optional[str]]:
        """Require a legal citation from retrieved metadata when available.

        Old corpus chunks may not have a citation; in that case this check is
        skipped. For An Phú, every chunk has at least ``citation_label``.
        """
        internal = self.INTERNAL_REFERENCE_RE.search(answer)
        if internal:
            return False, f"Contains internal reference: {internal.group(0)}"

        url = self.URL_RE.search(answer)
        if url:
            return False, f"Contains URL: {url.group(0)}"

        if self.NO_INFO_RE.search(answer):
            return True, None

        numbers = []
        labels = []
        for chunk in chunks:
            metadata = chunk.metadata or {}
            number = str(metadata.get("doc_number") or "").strip()
            label = str(
                metadata.get("citation") or metadata.get("citation_label") or ""
            ).strip()
            if number:
                numbers.append(number)
            elif label:
                labels.append(label)

        if not numbers and not labels:
            return True, None

        answer_norm = self._normalize_citation_text(answer)
        for number in numbers:
            if self._normalize_citation_text(number) in answer_norm:
                return True, None
        for label in labels:
            for candidate in self._label_candidates(label):
                if self._normalize_citation_text(candidate) in answer_norm:
                    return True, None

        return False, "Missing legal citation from retrieved context"

    def _label_candidates(self, label: str) -> List[str]:
        """Full label plus its identifying tail after the local prefix.

        Schedule/profile labels look like "Lịch làm việc UBND phường An Phú:
        Lịch làm việc HĐND - UBND ngày 12/01/2026 đến 17/01/2026". The model
        often cites only the part after the colon, which still uniquely
        identifies the document (dates/numbers), so accept it too.
        """
        candidates = [label]
        if ":" in label:
            tail = label.split(":", 1)[1].strip()
            # Only a substantial tail counts; short fragments could match
            # unrelated text and weaken the hallucination guard.
            if len(self._normalize_citation_text(tail)) >= 20:
                candidates.append(tail)
        return candidates

    def _check_confidence(self, answer: str) -> Tuple[bool, Optional[str]]:
        """
        Check answer doesn't contain uncertain language.
        
        Uncertain phrases indicate the model is guessing,
        which increases hallucination risk.
        """
        answer_lower = answer.lower()
        
        # Check for forbidden phrases
        found_phrases = [
            phrase for phrase in self.FORBIDDEN_PHRASES
            if phrase in answer_lower
        ]
        
        if found_phrases:
            return False, f"Contains uncertain language: {', '.join(found_phrases)}"
        
        return True, None
    
    def _extract_terms(self, text: str) -> Set[str]:
        """
        Extract meaningful terms from text.
        
        Extracts:
        - Words with 3+ characters
        - Preserves Vietnamese words
        - Removes common stop words (basic list)
        """
        # Simple Vietnamese stop words (expandable)
        stop_words = {
            'của', 'và', 'các', 'được', 'cho', 'từ', 'với',
            'trong', 'theo', 'này', 'đó', 'những', 'một'
        }
        
        # Extract words (3+ chars)
        words = re.findall(r'\b\w{3,}\b', text)
        
        # Filter stop words
        terms = {word for word in words if word not in stop_words}
        
        return terms
