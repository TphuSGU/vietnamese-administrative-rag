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

RUN_REAL_LLM_TESTS = os.getenv("RUN_REAL_LLM_TESTS") == "1"
REAL_LLM_REASON = "Set RUN_REAL_LLM_TESTS=1 to run live Gemini API tests"


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
    assert llm_service.MODEL_NAME.startswith("gemini-")
    # Tham số lấy từ .env qua settings, không hardcode trong code/test
    from app.core.config import settings
    assert llm_service.MODEL_NAME == settings.gemini_model
    assert llm_service.MAX_TOKENS == settings.max_tokens
    assert llm_service.TEMPERATURE == settings.temperature


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
                "chunk_index": 0,
                "citation_label": "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025 của HĐND phường An Phú",
                "citation": "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025 của HĐND phường An Phú, Điều 10"
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
    
    # Verify legal citation is the only source label (Req 9.3)
    assert "NGUỒN PHÁP LÝ:" in prompt
    assert "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025" in prompt
    assert "Điều 10" in prompt
    assert "Văn bản tham khảo chưa có số hiệu" in prompt
    assert "Đăng ký hộ khẩu" in prompt
    assert "[Tài liệu" not in prompt
    assert "document_id" not in prompt
    assert "chunk:" not in prompt
    assert "Điều 11" not in prompt
    
    # Verify query is included (Req 9.2)
    assert "Cần giấy tờ gì" in prompt
    
    # Verify system instructions present
    assert "trợ lý AI" in prompt
    assert "chính quyền" in prompt


def test_prompt_strips_internal_uuid_and_adds_procedure_citation_rule():
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            llm_service = LLMService(api_key='test_key')

    chunks = [
        RetrievedChunk(
            text='Mã thủ tục: 2.001019\nLệ phí: 50000 019b3fb2-b5b8-70ac-85e2-9409ec1eaffa',
            similarity_score=0.9,
            metadata={
                'document_id': 'dvc_procedure_1',
                'chunk_index': 0,
                'citation': 'Thủ tục Chứng thực di chúc, mã 2.001019, Cổng DVC quốc gia',
            },
        )
    ]
    prompt = llm_service._build_prompt('Chứng thực di chúc lệ phí bao nhiêu?', chunks)

    assert '019b3fb2-b5b8-70ac-85e2-9409ec1eaffa' not in prompt
    assert '50000 VNĐ' in prompt
    assert 'Mã thủ tục:' not in prompt
    assert 'Thủ tục <tên>, Cổng DVC quốc gia' in prompt


def test_prompt_without_citation_uses_generic_source():
    """Test prompt fallback when a chunk has no legal citation."""
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
    
    # Should handle missing citation without exposing internal IDs.
    assert "Văn bản tham khảo chưa có số hiệu" in prompt
    assert "Test content" in prompt
    assert "document_id" not in prompt


@pytest.mark.skipif(not RUN_REAL_LLM_TESTS, reason=REAL_LLM_REASON)
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
    assert result.model.startswith("gemini-")
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
    assert result.model.startswith("gemini-")


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
@pytest.mark.skipif(not RUN_REAL_LLM_TESTS, reason=REAL_LLM_REASON)
def test_answer_with_multiple_chunks(llm_service):
    """Test answer generation with multiple document chunks."""
    chunks = [
        RetrievedChunk(
            text="Điều kiện đăng ký: Phải là công dân Việt Nam, có nơi cư trú ổn định.",
            similarity_score=0.95,
            metadata={
                "document_id": "doc_1",
                "heading_context": "Điều 10: Thủ tục đăng ký",
                "chunk_index": 0,
                "citation_label": "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025 của HĐND phường An Phú"
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
                "chunk_index": 0,
                "citation": "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026",
                "doc_number": "25/NQ-HĐND",
                "issued_date": "2026-07-29",
                "issuer": "HĐND phường An Phú",
                "doc_scope": "local",
                "doc_type": "Nghị quyết",
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
    # Citation metadata flows to the reference (Phase 8)
    assert ref.citation == "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026"
    assert ref.doc_number == "25/NQ-HĐND"
    assert ref.issued_date == "2026-07-29"
    assert ref.issuer == "HĐND phường An Phú"
    assert ref.doc_scope == "local"
    assert ref.doc_type == "Nghị quyết"


def test_chunk_reference_citation_falls_back_to_label():
    """citation uses citation_label when the chunk has no explicit citation."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_response = Mock()
            mock_response.text = "Test answer"
            mock_model.return_value.generate_content.return_value = mock_response
            llm_service = LLMService(api_key="test_key")

    chunks = [
        RetrievedChunk(
            text="Nội dung",
            similarity_score=0.8,
            metadata={
                "document_id": "doc_2",
                "chunk_index": 1,
                "citation_label": "Thông báo của UBND phường An Phú ngày 29/6/2026",
                "doc_number": "",
                "issued_date": "2026-06-29",
                "issuer": "",
                "doc_scope": "local",
            }
        )
    ]

    result = llm_service.generate_answer("Test query", chunks)
    ref = result.source_chunks[0]
    assert ref.citation == "Thông báo của UBND phường An Phú ngày 29/6/2026"
    assert ref.doc_number == ""
    assert ref.doc_scope == "local"


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


def test_generate_answer_returns_raw_model_text():
    """Câu trả lời thật phải tới pipeline, không bị thay bằng câu fallback."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_response = Mock()
            mock_response.text = "Paris là thủ đô của nước Pháp."
            mock_model.return_value.generate_content.return_value = mock_response

            llm_service = LLMService(api_key="test_key")

    chunks = [
        RetrievedChunk(
            text="Nghị quyết quy định mục tiêu an sinh xã hội trên địa bàn phường.",
            similarity_score=0.9,
            metadata={"document_id": "doc_1", "chunk_index": 0},
        )
    ]

    result = llm_service.generate_answer("Câu hỏi kiểm thử hợp lệ", chunks)

    # Không còn validate/thay thế trong LLMService: pipeline mới là nơi quyết định
    assert result.answer == "Paris là thủ đô của nước Pháp."


def test_generate_answer_without_context_has_no_documents():
    """Fallback khi không truy xuất được: prompt không có block tài liệu."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_response = Mock()
            mock_response.text = (
                "Chưa có thông tin chính thức trong tài liệu của địa phương "
                "(nguồn tổng quát, không có trong tài liệu)."
            )
            mock_model.return_value.generate_content.return_value = mock_response

            llm_service = LLMService(api_key="test_key")

    result = llm_service.generate_answer_without_context(
        "Thủ tục đăng ký khai sinh ở đâu?"
    )

    assert isinstance(result, GeneratedAnswer)
    assert result.source_chunks == []
    assert result.model.startswith("gemini-")
    assert result.tokens_used > 0

    prompt = mock_model.return_value.generate_content.call_args[0][0]
    assert "CÁC TÀI LIỆU THAM KHẢO" not in prompt
    assert "Thủ tục đăng ký khai sinh ở đâu?" in prompt
    assert "không lấy từ tài liệu của địa phương" in prompt


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
@pytest.mark.skipif(not RUN_REAL_LLM_TESTS, reason=REAL_LLM_REASON)
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
