"""
LLM Service for answer generation using Gemini API.
Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 15.3
"""

import os
import re
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

import google.generativeai as genai

from app.models.data_models import RetrievedChunk, GeneratedAnswer, ChunkReference
from app.core.config import settings
from app.core.logging import get_logger
from app.models.exceptions import LLMGenerationError

logger = get_logger(__name__)


class LLMService:
    """
    LLM service for answer generation using Google Gemini API.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
    """
    
    MAX_TOKENS = settings.max_tokens
    TEMPERATURE = settings.temperature
    # settings đã đọc .env (load_dotenv trong config) nên không cần hardcode tên model
    MODEL_NAME = settings.gemini_model
    UUID_RE = re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    )
    PROCEDURE_CODE_RE = re.compile(
        r"(?im)^\s*Mã thủ tục:\s*[^\n]*\n?",
    )
    
    SYSTEM_INSTRUCTION = """Bạn là trợ lý AI hỗ trợ công dân tra cứu thông tin về văn bản chính quyền địa phương.

Nhiệm vụ của bạn:
1. Trả lời câu hỏi dựa CHÍNH XÁC trên các tài liệu được cung cấp
2. Trả lời HOÀN TOÀN bằng tiếng Việt
3. Trả lời trực tiếp vào nội dung trước; trích dẫn nguồn ngắn gọn trong ngoặc hoặc ngay sau ý, ví dụ: "UBND phường An Phú làm việc từ 07:30 đến 17:00 (Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú)." Không mở đầu bằng "Theo ..." nếu không cần.
4. Nếu thông tin không đủ, hãy nói rõ "Tôi không tìm thấy thông tin đầy đủ trong các tài liệu được cung cấp"
5. Viết tự nhiên, ngắn gọn (2–5 câu), đi thẳng vào câu trả lời; tránh mở đầu máy móc, tránh heading/bullet không cần và tránh lặp lại toàn bộ tiêu đề văn bản dài

LƯU Ý QUAN TRỌNG:
- KHÔNG tự suy đoán hoặc tạo thông tin không có trong tài liệu
- Được phép tổng hợp/so sánh thông tin trong cùng tài liệu khi kết luận rút ra trực tiếp; không thêm kiến thức ngoài tài liệu
- KHÔNG trả lời về chủ đề không liên quan đến hành chính công
- CHỈ sử dụng thông tin từ các tài liệu được cung cấp bên dưới
- Chỉ trích dẫn theo trường "NGUỒN PHÁP LÝ"; không dùng nhãn đánh số tài liệu, mã nội bộ, số thứ tự đoạn hoặc tên file
- Không thêm mục nguồn ở cuối câu trả lời
- Nếu nguồn ghi "Văn bản tham khảo chưa có số hiệu", không được bịa số hiệu
- Với thủ tục hành chính, trích dẫn dạng "Thủ tục <tên>, Cổng DVC quốc gia"; KHÔNG đưa mã thủ tục vào câu trả lời
- Nếu người dùng chỉ chào hỏi/giới thiệu, trả lời ngắn và KHÔNG liệt kê tài liệu, mã văn bản hoặc nguồn
- Không hiển thị UUID, mã kỹ thuật hoặc mã tiền tệ nội bộ trong câu trả lời"""

    # Dùng khi retrieval không trả về chunk nào: vẫn hỏi LLM nhưng bắt model
    # ghi rõ đây không phải thông tin lấy từ tài liệu địa phương.
    NO_CONTEXT_INSTRUCTION = """Bạn là trợ lý AI trả lời câu hỏi của người dân KHÔNG có tài liệu địa phương nào được truy xuất.

Nhiệm vụ:
1. Trả lời HOÀN TOÀN bằng tiếng Việt, ngắn gọn (2-5 câu), đi thẳng vào nội dung.
2. Bắt buộc nói rõ câu trả lời không lấy từ tài liệu của địa phương, đặt trong ngoặc ở cuối ý, ví dụ: "... (nguồn tổng quát, không có trong tài liệu của phường)".
3. Chỉ trả lời câu hỏi chung, kiến thức tổng quát mà bạn chắc chắn. Nếu là thông tin riêng của một địa phương, một văn bản, một thủ tục cụ thể, hãy nói "Tôi không tìm thấy thông tin trong tài liệu của địa phương" và gợi ý liên hệ UBND phường để được trả lời chính thức.
4. KHÔNG bịa số hiệu văn bản, ngày ban hành, tên lãnh đạo, mức phí hoặc thời gian giải quyết cụ thể.
5. KHÔNG hiển thị UUID, mã kỹ thuật hoặc mã tiền tệ nội bộ trong câu trả lời."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM service with Gemini API.
        
        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Gemini API key not provided. "
                "Set GEMINI_API_KEY environment variable or pass api_key parameter."
            )
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.MODEL_NAME,
            generation_config={
                "temperature": self.TEMPERATURE,
                "max_output_tokens": self.MAX_TOKENS,
            }
        )
        
        # Output validation belongs to the pipeline (single threshold). Doing it
        # here too made the pipeline validate a substituted fallback text instead
        # of the model's real answer.
        logger.info(
            f"LLMService initialized with {self.MODEL_NAME}",
            extra={
                "max_tokens": self.MAX_TOKENS,
                "temperature": self.TEMPERATURE,
            }
        )
    
    def _build_prompt(
        self, 
        query: str, 
        retrieved_chunks: List[RetrievedChunk]
    ) -> str:
        """
        Build prompt with system instruction, context, and query.
        
        Args:
            query: User query
            retrieved_chunks: Retrieved document chunks
            
        Returns:
            Complete prompt string
            
        Validates: Requirements 9.2, 9.3
        """
        # Format context from retrieved chunks (Req 9.3)
        context_parts = []
        for chunk in retrieved_chunks:
            chunk_citation = (chunk.metadata.get("citation") or "").strip()
            citation_label = (chunk.metadata.get("citation_label") or "").strip()
            source = chunk_citation or citation_label or "Văn bản tham khảo chưa có số hiệu"
            safe_text = self.UUID_RE.sub("VNĐ", chunk.text or "")
            safe_text = self.PROCEDURE_CODE_RE.sub("", safe_text)
            context_parts.append(
                f"NGUỒN PHÁP LÝ: {source}\n"
                f"NỘI DUNG:\n{safe_text}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build complete prompt (Req 9.2)
        prompt = f"""{self.SYSTEM_INSTRUCTION}

---

CÁC TÀI LIỆU THAM KHẢO:

{context}

---

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}

TRẢ LỜI (bằng tiếng Việt, dựa trên tài liệu trên):"""
        
        return prompt
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _call_gemini_api(self, prompt: str) -> str:
        """
        Call Gemini API with retry logic.
        
        Args:
            prompt: Complete prompt
            
        Returns:
            Generated answer text
            
        Validates: Requirement 15.3 (retry logic)
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    def generate_answer(
        self, 
        query: str, 
        retrieved_chunks: List[RetrievedChunk]
    ) -> GeneratedAnswer:
        """
        Generate answer using Gemini LLM.
        
        Args:
            query: User query
            retrieved_chunks: Retrieved document chunks
            
        Returns:
            GeneratedAnswer with answer text and metadata
            
        Validates: Requirements 9.1, 9.4, 9.5, 9.6, 9.7
        """
        # Handle insufficient information (Req 9.6)
        if not retrieved_chunks:
            return GeneratedAnswer(
                answer="Tôi không tìm thấy tài liệu liên quan đến câu hỏi của bạn trong cơ sở dữ liệu.",
                source_chunks=[],
                model=self.MODEL_NAME,
                tokens_used=0
            )
        
        # Build prompt (Req 9.2, 9.3)
        prompt = self._build_prompt(query, retrieved_chunks)
        
        logger.info(
            "Generating answer",
            extra={
                "query": query[:50],
                "num_chunks": len(retrieved_chunks),
                "prompt_length": len(prompt)
            }
        )
        
        # Generate with retry (Req 9.1, 15.3). No validation/substitution here:
        # the pipeline validates this exact text, otherwise a "not found"
        # placeholder is what gets checked and honest answers fail.
        try:
            answer_text = self._call_gemini_api(prompt)
        except Exception as e:
            logger.error(f"Answer generation failed after retries: {e}")
            raise LLMGenerationError(f"Failed to generate answer: {e}")
        
        # Estimate tokens (Gemini doesn't provide exact count)
        estimated_tokens = len(answer_text.split())
        
        logger.info(
            "Answer generated",
            extra={
                "answer_length": len(answer_text),
                "estimated_tokens": estimated_tokens
            }
        )
        
        # Create chunk references, carrying citation metadata through to the
        # API so source cards never rely on the LLM to repeat document numbers.
        chunk_references = []
        for chunk in retrieved_chunks:
            meta = chunk.metadata or {}
            chunk_references.append(
                ChunkReference(
                    document_id=chunk.document_id,
                    text=chunk.text[:200],  # First 200 chars as preview
                    similarity_score=chunk.similarity_score,
                    chunk_index=chunk.chunk_index,
                    citation=str(
                        meta.get("citation") or meta.get("citation_label") or ""
                    ).strip(),
                    doc_number=str(meta.get("doc_number") or "").strip(),
                    issued_date=str(meta.get("issued_date") or "").strip(),
                    issuer=str(meta.get("issuer") or "").strip(),
                    doc_scope=str(meta.get("doc_scope") or "").strip(),
                    doc_type=str(meta.get("doc_type") or "").strip(),
                )
            )
        
        # Return result (Req 9.4, 9.7)
        return GeneratedAnswer(
            answer=answer_text,
            source_chunks=chunk_references,
            model=self.MODEL_NAME,
            tokens_used=estimated_tokens
        )

    def generate_answer_without_context(self, query: str) -> GeneratedAnswer:
        """
        Answer directly with the LLM when RAG retrieval is unusable
        (no chunks returned or retrieval errored).

        The answer carries no source chunks and is required to state that it
        does not come from local documents, so it cannot be mistaken for a
        grounded RAG answer.

        Args:
            query: User question in Vietnamese

        Returns:
            GeneratedAnswer with empty source_chunks
        """
        prompt = f"""{self.NO_CONTEXT_INSTRUCTION}

---

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}

TRẢ LỜI (bằng tiếng Việt):"""

        logger.info(
            "Generating answer without RAG context",
            extra={"query": query[:50]}
        )

        try:
            answer_text = self._call_gemini_api(prompt)
        except Exception as e:
            logger.error(f"Direct answer generation failed after retries: {e}")
            raise LLMGenerationError(f"Failed to generate answer: {e}")

        return GeneratedAnswer(
            answer=answer_text,
            source_chunks=[],
            model=self.MODEL_NAME,
            tokens_used=len(answer_text.split())
        )
