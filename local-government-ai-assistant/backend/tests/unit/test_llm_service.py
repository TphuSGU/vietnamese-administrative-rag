"""
Unit tests for LLM Service with Gemini API.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 15.3**
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from app.rag.generation.llm_service import LLMService
from app.models.data_models import RetrievedChunk, GeneratedAnswer, ChunkReference
from app.models.exceptions import LLMGenerationError


@pytest.fixture
def llm_service():
    """Create LLM service with real API key if available."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    return LLMService(api_key=api_key)


def test_llm_service_initialization(llm_service):
    """
    Test LLM service initializes correctly.
    
    **Validates: Requirement 9.1**
    """
    assert llm_service.api_key is not None
    assert llm_service.model is not None
    assert llm_service.MODEL_NAME == "gemini-2.0-flash-exp"
    assert llm_service.MAX_TOKENS == 500
    assert llm_service.TEMPERATURE == 0.3


def test_llm_service_initialization_without_api_key():
    """Test that LLM service raises error without API key."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove GEMINI_API_KEY from environment
        with pytest.raises(ValueError, match="API key not provided"):
            LLMService(api_key=None)


def test_prompt_construction():
    """
    Test prompt building with Vietnamese instructions.
    
    **Validates: Requirements 9.2, 9.3**
    """
    # Create service with dummy key for testing
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            llm_service = LLMService(api_key="test_key")
    
    chunks = [
        RetrievedChunk(
            text="Đăng ký hộ khẩu cần CMND, CCCD, sổ hộ khẩu cũ.",
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 10: Thủ tục đăng ký",
                "chunk_index": 0
            }
        ),
        RetrievedChunk(
            text="Thời gian giải quyết là 3 ngày làm việc.",
            similarity_score=0.85,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 11: Thời gian xử lý",
                "chunk_index": 1
            }
        )
    ]
    
    prompt = llm_service._build_prompt("Cần giấy tờ gì để đăng ký hộ khẩu?", chunks)
    
    # Verify Vietnamese instructions present (Req 9.4)
    assert "tiếng Việt" in prompt
    assert "tài liệu" in prompt.lower()
    
    # Verify chunks are formatted (Req 9.3)
    assert "[Tài liệu 1]" in prompt
    assert "[Tài liệu 2]" in prompt
    assert "Điều 10" in prompt
    assert "Điều 11" in prompt
    assert "Đăng ký hộ khẩu" in prompt
    
    # Verify query is included (Req 9.2)
    assert "Cần giấy tờ gì" in prompt
    
    # Verify system instructions present
    assert "trợ lý AI" in prompt
    assert "chính quyền" in prompt


def test_prompt_with_missing_heading_context():
    """Test prompt construction when heading context is missing."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            llm_service = LLMService(api_key="test_key")
    
    chunks = [
        RetrievedChunk(
            text="Test content without heading",
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "chunk_index": 0
            }
        )
    ]
    
    prompt = llm_service._build_prompt("Test query", chunks)
    
    # Should handle missing heading gracefully
    assert "Không có tiêu đề" in prompt
    assert "Test content" in prompt


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_generate_answer_with_real_api(llm_service):
    """
    Test answer generation with real Gemini API.
    
    **Validates: Requirements 9.1, 9.4, 9.6, 9.7**
    """
    chunks = [
        RetrievedChunk(
            text="Đăng ký hộ khẩu thường trú cần: CMND/CCCD, sổ hộ khẩu cũ, giấy xác nhận cư trú.",
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 10: Thủ tục đăng ký",
                "chunk_index": 0
            }
        )
    ]
    
    result = llm_service.generate_answer(
        "Đăng ký hộ khẩu cần giấy tờ gì?",
        chunks
    )
    
    # Verify response structure (Req 9.7)
    assert isinstance(result, GeneratedAnswer)
    assert result.answer is not None
    assert len(result.answer) > 0
    assert result.model == "gemini-2.0-flash-exp"
    assert result.tokens_used > 0
    assert len(result.source_chunks) > 0
    
    # Verify Vietnamese response (Req 9.4)
    answer_lower = result.answer.lower()
    # Answer should contain relevant Vietnamese keywords
    assert any(word in answer_lower for word in ["cmnd", "cccd", "giấy tờ", "hộ khẩu", "cần"])
    
    # Verify source chunks are referenced
    assert len(result.source_chunks) == 1
    assert result.source_chunks[0].document_id == "doc_1"


def test_insufficient_information_handling():
    """
    Test handling when no chunks provided.
    
    **Validates: Requirement 9.5 (insufficient information)
    """
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            llm_service = LLMService(api_key="test_key")
    
    result = llm_service.generate_answer(
        "Test query",
        []  # Empty chunks
    )
    
    # Should return appropriate message (Req 9.5)
    assert "không tìm thấy" in result.answer.lower() or "không có tài liệu" in result.answer.lower()
    assert len(result.source_chunks) == 0
    assert result.tokens_used == 0
    assert result.model == "gemini-2.0-flash-exp"


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_answer_with_multiple_chunks(llm_service):
    """Test answer generation with multiple document chunks."""
    chunks = [
        RetrievedChunk(
            text="Điều kiện đăng ký: Phải là công dân Việt Nam, có nơi cư trú ổn định.",
            similarity_score=0.95,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 5: Điều kiện",
                "chunk_index": 0
            }
        ),
        RetrievedChunk(
            text="Hồ sơ gồm: CMND, sổ hộ khẩu cũ, giấy chứng nhận cư trú.",
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 6: Hồ sơ",
                "chunk_index": 1
            }
        ),
        RetrievedChunk(
            text="Thời gian giải quyết: 3 ngày làm việc kể từ ngày nhận hồ sơ hợp lệ.",
            similarity_score=0.85,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 7: Thời gian",
                "chunk_index": 2
            }
        )
    ]
    
    result = llm_service.generate_answer(
        "Quy trình đăng ký hộ khẩu như thế nào?",
        chunks
    )
    
    # Verify answer is generated
    assert len(result.answer) > 0
    assert result.tokens_used > 0
    
    # Verify all chunks are referenced
    assert len(result.source_chunks) == 3
    assert all(chunk.document_id == "doc_1" for chunk in result.source_chunks)


def test_chunk_reference_creation():
    """Test that chunk references are created correctly."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            # Mock the generate_content response
            mock_response = Mock()
            mock_response.text = "Test answer in Vietnamese"
            mock_model.return_value.generate_content.return_value = mock_response
            
            llm_service = LLMService(api_key="test_key")
    
    chunks = [
        RetrievedChunk(
            text="Long text " * 50,  # Long text to test preview
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "chunk_index": 0
            }
        )
    ]
    
    result = llm_service.generate_answer("Test query", chunks)
    
    # Verify chunk reference is created
    assert len(result.source_chunks) == 1
    ref = result.source_chunks[0]
    assert isinstance(ref, ChunkReference)
    assert ref.document_id == "doc_1"
    assert ref.chunk_index == 0
    assert ref.similarity_score == 0.9
    # Text should be preview (first 200 chars)
    assert len(ref.text) <= 200


def test_api_error_handling():
    """
    Test handling of API errors with retry logic.
    
    **Validates: Requirement 15.3 (retry logic)**
    """
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            # Mock API to always fail
            mock_model.return_value.generate_content.side_effect = Exception("API Error")
            
            llm_service = LLMService(api_key="test_key")
    
    chunks = [
        RetrievedChunk(
            text="Test",
            similarity_score=0.9,
            metadata={"document_id": "doc_1"}
        )
    ]
    
    # Should raise LLMGenerationError after retries
    with pytest.raises(LLMGenerationError, match="Failed to generate answer"):
        llm_service.generate_answer("Test query", chunks)


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_vietnamese_response_enforcement(llm_service):
    """
    Test that responses are in Vietnamese.
    
    **Validates: Requirement 9.4**
    """
    chunks = [
        RetrievedChunk(
            text="Người dân cần mang theo CMND khi đăng ký.",
            similarity_score=0.9,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 1",
                "chunk_index": 0
            }
        )
    ]
    
    result = llm_service.generate_answer(
        "Cần mang gì khi đăng ký?",
        chunks
    )
    
    # Response should be in Vietnamese - check for Vietnamese words
    answer = result.answer
    # Should contain Vietnamese characters or common Vietnamese words
    vietnamese_indicators = ["cmnd", "cần", "mang", "đăng ký", "người", "tài liệu"]
    assert any(indicator in answer.lower() for indicator in vietnamese_indicators)
