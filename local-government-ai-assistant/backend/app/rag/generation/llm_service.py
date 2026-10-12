"""
LLM Service for answer generation using Gemini API.
Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 15.3
"""

import os
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

import google.generativeai as genai

from app.models.data_models import RetrievedChunk, GeneratedAnswer, ChunkReference
from app.core.logging import get_logger
from app.models.exceptions import LLMGenerationError

logger = get_logger(__name__)


class LLMService:
    """
    LLM service for answer generation using Google Gemini API.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
    """
    
    MAX_TOKENS = 500
    TEMPERATURE = 0.3
    MODEL_NAME = "gemini-2.0-flash-exp"
    
    SYSTEM_INSTRUCTION = """Bạn là trợ lý AI hỗ trợ công dân tra cứu thông tin về văn bản chính quyền địa phương.

Nhiệm vụ của bạn:
1. Trả lời câu hỏi dựa CHÍNH XÁC trên các tài liệu được cung cấp
2. Trả lời HOÀN TOÀN bằng tiếng Việt
3. Trích dẫn nguồn tài liệu khi trả lời (ví dụ: "Theo Tài liệu 1...")
4. Nếu thông tin không đủ, hãy nói rõ "Tôi không tìm thấy thông tin đầy đủ trong các tài liệu được cung cấp"

LƯU Ý QUAN TRỌNG:
- KHÔNG tự suy đoán hoặc tạo thông tin không có trong tài liệu
- KHÔNG trả lời về chủ đề không liên quan đến hành chính công
- CHỈ sử dụng thông tin từ các tài liệu được cung cấp bên dưới"""
    
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
        
        logger.info(
            f"LLMService initialized with {self.MODEL_NAME}",
            extra={"max_tokens": self.MAX_TOKENS, "temperature": self.TEMPERATURE}
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
        for i, chunk in enumerate(retrieved_chunks, 1):
            heading = chunk.heading_context or "Không có tiêu đề"
            context_parts.append(
                f"[Tài liệu {i}] ({heading}):\n{chunk.text}"
            )
        
        context = "\n\n".join(context_parts)
        
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
        
        # Generate answer with retry (Req 9.1, 15.3)
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
        
        # Create chunk references
        chunk_references = [
            ChunkReference(
                document_id=chunk.document_id,
                text=chunk.text[:200],  # First 200 chars as preview
                similarity_score=chunk.similarity_score,
                chunk_index=chunk.chunk_index
            )
            for chunk in retrieved_chunks
        ]
        
        # Return result (Req 9.4, 9.7)
        return GeneratedAnswer(
            answer=answer_text,
            source_chunks=chunk_references,
            model=self.MODEL_NAME,
            tokens_used=estimated_tokens
        )
