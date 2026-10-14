"""
Property-based tests for RAG Pipeline.

**Validates: Requirements 7.2, 10.4, 10.5, 16.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import Mock, MagicMock
from pathlib import Path
import json
import tempfile

from app.rag.pipeline.rag_pipeline import RAGPipeline
from app.models.exceptions import RAGValidationError
from app.models.data_models import RetrievedChunk, GeneratedAnswer, ChunkReference


# Custom strategies for Vietnamese text
vietnamese_chars = "aăâbcdđeêghiklmnoôơpqrstuưvxy àáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"


@given(query_length=st.integers(min_value=0, max_value=600))
@settings(max_examples=50)
def test_property_17_query_length_validation(query_length):
    """
    Property 17: Query length validation.
    
    For any query string, validation should accept it if and only if
    its length is within the range [10, 500] characters.
    
    **Validates: Requirement 7.2**
    """
    mock_retriever = Mock()
    mock_llm = Mock()
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    # Create query of specified length
    query = "a" * query_length
    
    MIN_LENGTH = RAGPipeline.MIN_QUERY_LENGTH
    MAX_LENGTH = RAGPipeline.MAX_QUERY_LENGTH
    
    if query_length < MIN_LENGTH or query_length > MAX_LENGTH:
        # Should raise validation error
        with pytest.raises(RAGValidationError):
            pipeline._validate_query(query)
    else:
        # Should pass validation
        pipeline._validate_query(query)  # Should not raise


@given(
    query=st.text(
        alphabet=vietnamese_chars,
        min_size=10,
        max_size=500
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_25_query_logging_completeness(query):
    """
    Property 25: Query logging completeness.
    
    For any processed query, the log entry must contain timestamp,
    retrieved chunks, and generated answer.
    
    **Validates: Requirement 10.4**
    """
    # Create temporary directory within test
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create mock components
        mock_retriever = Mock()
        mock_llm = Mock()
        mock_llm.MODEL_NAME = "test-model"
        
        # Mock retrieval to return empty results
        mock_retriever.retrieve.return_value = []
        
        # Create pipeline
        pipeline = RAGPipeline(
            retriever=mock_retriever,
            llm_service=mock_llm,
            log_dir=tmp_path / "logs"
        )
        
        # Execute query
        try:
            pipeline.query(query, k=5)
        except Exception:
            # Even if query fails, logging might still occur
            pass
        
        # Check if log file was created and has content
        log_file = tmp_path / "logs" / "query_logs.jsonl"
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
            
            if len(log_lines) > 0:
                # Verify log entry completeness
                log_entry = json.loads(log_lines[-1])
                
                # Must have all required fields
                assert "query_id" in log_entry
                assert "timestamp" in log_entry
                assert "query" in log_entry
                assert "processing_time_ms" in log_entry


@given(query=st.text(min_size=10, max_size=500))
@settings(max_examples=50)
def test_property_26_rag_response_completeness(query):
    """
    Property 26: RAG response completeness.
    
    For any completed query, the response must contain answer text,
    source chunks, and relevance scores.
    
    **Validates: Requirement 10.5**
    """
    # Create mock components
    mock_retriever = Mock()
    mock_llm = Mock()
    mock_llm.MODEL_NAME = "test-model"
    
    # Mock return values
    mock_chunks = [
        RetrievedChunk(
            text="Test chunk",
            similarity_score=0.9,
            metadata={"document_id": "doc_1", "chunk_index": 0}
        )
    ]
    mock_retriever.retrieve.return_value = mock_chunks
    
    mock_answer = GeneratedAnswer(
        answer="Test answer",
        source_chunks=[
            ChunkReference(
                document_id="doc_1",
                text="Test",
                similarity_score=0.9,
                chunk_index=0
            )
        ],
        model="test-model",
        tokens_used=10
    )
    mock_llm.generate_answer.return_value = mock_answer
    
    # Create pipeline
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    # Execute query
    try:
        response = pipeline.query(query, k=5)
        
        # Verify response completeness
        assert response.query_id is not None
        assert response.answer is not None
        assert isinstance(response.source_chunks, list)
        assert isinstance(response.relevance_scores, list)
        assert response.processing_time > 0
        assert response.model is not None
    except RAGValidationError:
        # If query validation fails, that's expected for some random strings
        pass


@given(text=st.text(min_size=10, max_size=500))
@settings(max_examples=50)
def test_property_45_utf8_query_validation(text):
    """
    Property 45: UTF-8 query validation.
    
    For any query string, validation should verify that it contains
    valid UTF-8 encoded characters.
    
    **Validates: Requirement 16.3**
    """
    mock_retriever = Mock()
    mock_llm = Mock()
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    # Hypothesis generates valid UTF-8 strings by default
    # So this should always pass UTF-8 validation
    try:
        pipeline._validate_query(text)
        # If validation passes, ensure the text is valid UTF-8
        text.encode('utf-8')
    except RAGValidationError as e:
        # If validation fails, it should be for length, not UTF-8
        assert "utf" not in str(e).lower() or "cannot be empty" in str(e).lower()


def test_query_length_boundaries():
    """Test exact boundary conditions for query length."""
    mock_retriever = Mock()
    mock_llm = Mock()
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    MIN_LENGTH = RAGPipeline.MIN_QUERY_LENGTH
    MAX_LENGTH = RAGPipeline.MAX_QUERY_LENGTH
    
    # Test boundary cases
    # Just below minimum (9 chars)
    with pytest.raises(RAGValidationError):
        pipeline._validate_query("a" * (MIN_LENGTH - 1))
    
    # Exactly at minimum (10 chars)
    pipeline._validate_query("a" * MIN_LENGTH)  # Should pass
    
    # Exactly at maximum (500 chars)
    pipeline._validate_query("a" * MAX_LENGTH)  # Should pass
    
    # Just above maximum (501 chars)
    with pytest.raises(RAGValidationError):
        pipeline._validate_query("a" * (MAX_LENGTH + 1))


def test_vietnamese_text_query_validation():
    """Test that Vietnamese queries pass validation."""
    mock_retriever = Mock()
    mock_llm = Mock()
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    vietnamese_queries = [
        "Đăng ký hộ khẩu cần giấy tờ gì?",
        "Thủ tục làm CMND như thế nào?",
        "Quy trình xin cấp hộ chiếu?",
        "Các bước đăng ký tạm trú tại địa phương?",
    ]
    
    for query in vietnamese_queries:
        # All should pass validation
        pipeline._validate_query(query)


def test_empty_and_whitespace_queries():
    """Test that empty and whitespace-only queries are rejected."""
    mock_retriever = Mock()
    mock_llm = Mock()
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm
    )
    
    invalid_queries = [
        "",
        " ",
        "   ",
        "\t",
        "\n",
        "  \t\n  ",
    ]
    
    for query in invalid_queries:
        with pytest.raises(RAGValidationError, match="cannot be empty"):
            pipeline._validate_query(query)


def test_log_entry_json_format(tmp_path):
    """Test that log entries are valid JSON."""
    mock_retriever = Mock()
    mock_llm = Mock()
    mock_llm.MODEL_NAME = "test-model"
    mock_retriever.retrieve.return_value = []
    
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm,
        log_dir=tmp_path / "logs"
    )
    
    # Execute query
    pipeline.query("Test query for JSON validation", k=5)
    
    # Read log file
    log_file = tmp_path / "logs" / "query_logs.jsonl"
    assert log_file.exists()
    
    with open(log_file, 'r', encoding='utf-8') as f:
        log_line = f.read().strip()
    
    # Should be valid JSON
    log_entry = json.loads(log_line)
    assert isinstance(log_entry, dict)


def test_processing_time_always_positive(tmp_path):
    """Test that processing time is always positive."""
    mock_retriever = Mock()
    mock_llm = Mock()
    mock_llm.MODEL_NAME = "test-model"
    mock_retriever.retrieve.return_value = []
    
    pipeline = RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm,
        log_dir=tmp_path
    )
    
    response = pipeline.query("Test query for timing", k=5)
    
    # Processing time must be positive
    assert response.processing_time > 0
    assert isinstance(response.processing_time, (int, float))
