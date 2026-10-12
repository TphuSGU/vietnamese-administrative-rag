"""Integration tests for RAG Pipeline."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from app.rag.pipeline.rag_pipeline import RAGPipeline
from app.models.data_models import RetrievedChunk, GeneratedAnswer, ChunkReference, RAGResponse
from app.models.exceptions import RAGValidationError


@pytest.fixture
def mock_retriever():
    """Mock retriever."""
    retriever = Mock()
    return retriever


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    service = Mock()
    service.MODEL_NAME = "gemini-2.0-flash-exp"
    return service


@pytest.fixture
def rag_pipeline(mock_retriever, mock_llm_service, tmp_path):
    """Create RAG Pipeline instance."""
    return RAGPipeline(
        retriever=mock_retriever,
        llm_service=mock_llm_service,
        log_dir=tmp_path / "logs"
    )


def test_query_end_to_end(rag_pipeline, mock_retriever, mock_llm_service):
    """Test complete query processing end-to-end."""
    # Setup
    query = "Thủ tục đăng ký hộ khẩu cần những giấy tờ gì?"
    
    # Mock retrieved chunks
    mock_chunks = [
        RetrievedChunk(
            text="Giấy tờ cần có: CMND, sổ hộ khẩu cũ, đơn đăng ký",
            similarity_score=0.95,
            metadata={"document_id": "doc_1", "heading_context": "Điều 5"}
        ),
        RetrievedChunk(
            text="Thời gian giải quyết: 3 ngày làm việc",
            similarity_score=0.85,
            metadata={"document_id": "doc_1", "heading_context": "Điều 6"}
        )
    ]
    mock_retriever.retrieve.return_value = mock_chunks
    
    # Mock generated answer
    mock_answer = GeneratedAnswer(
        answer="Để đăng ký hộ khẩu, bạn cần: CMND, sổ hộ khẩu cũ, đơn đăng ký. Thời gian giải quyết là 3 ngày làm việc.",
        source_chunks=[
            ChunkReference(
                document_id="doc_1",
                text="Giấy tờ cần có...",
                similarity_score=0.95,
                chunk_index=0
            )
        ],
        model="gemini-2.0-flash-exp",
        tokens_used=45
    )
    mock_llm_service.generate_answer.return_value = mock_answer
    
    # Execute
    response = rag_pipeline.query(query, k=5)
    
    # Verify
    assert isinstance(response, RAGResponse)
    assert response.answer == mock_answer.answer
    assert len(response.source_chunks) > 0
    assert len(response.relevance_scores) == 2
    assert response.processing_time > 0
    assert response.model == "gemini-2.0-flash-exp"
    
    # Verify calls
    mock_retriever.retrieve.assert_called_once_with(query, k=5)
    mock_llm_service.generate_answer.assert_called_once()


def test_query_with_empty_results(rag_pipeline, mock_retriever, mock_llm_service):
    """Test query when retrieval returns no results."""
    # Setup
    query = "Không có tài liệu liên quan"
    mock_retriever.retrieve.return_value = []
    
    # Execute
    response = rag_pipeline.query(query)
    
    # Verify
    assert "Không tìm thấy tài liệu" in response.answer
    assert len(response.source_chunks) == 0
    assert len(response.relevance_scores) == 0
    
    # LLM should not be called
    mock_llm_service.generate_answer.assert_not_called()


def test_query_validation_empty_query(rag_pipeline):
    """Test that empty queries are rejected."""
    with pytest.raises(RAGValidationError, match="cannot be empty"):
        rag_pipeline.query("")
    
    with pytest.raises(RAGValidationError, match="cannot be empty"):
        rag_pipeline.query("   ")


def test_query_validation_too_short(rag_pipeline):
    """Test that too-short queries are rejected."""
    short_query = "abc"  # Less than MIN_QUERY_LENGTH (10)
    
    with pytest.raises(RAGValidationError, match="too short"):
        rag_pipeline.query(short_query)


def test_query_validation_too_long(rag_pipeline):
    """Test that too-long queries are rejected."""
    long_query = "a" * 501  # More than MAX_QUERY_LENGTH (500)
    
    with pytest.raises(RAGValidationError, match="too long"):
        rag_pipeline.query(long_query)


def test_query_logging(rag_pipeline, mock_retriever, mock_llm_service, tmp_path):
    """Test that queries are logged to file."""
    # Setup
    query = "Test query for logging"
    
    mock_chunks = [
        RetrievedChunk(
            text="Test chunk",
            similarity_score=0.9,
            metadata={"document_id": "doc_1"}
        )
    ]
    mock_retriever.retrieve.return_value = mock_chunks
    
    mock_answer = GeneratedAnswer(
        answer="Test answer",
        source_chunks=[],
        model="gemini-2.0-flash-exp",
        tokens_used=10
    )
    mock_llm_service.generate_answer.return_value = mock_answer
    
    # Execute
    response = rag_pipeline.query(query)
    
    # Verify log file exists
    log_file = tmp_path / "logs" / "query_logs.jsonl"
    assert log_file.exists()
    
    # Verify log content
    import json
    with open(log_file, 'r', encoding='utf-8') as f:
        log_lines = f.readlines()
    
    assert len(log_lines) > 0
    log_entry = json.loads(log_lines[-1])
    assert log_entry["query"] == query
    assert log_entry["query_id"] == response.query_id
    assert "processing_time_ms" in log_entry


def test_retrieval_failure_handling(rag_pipeline, mock_retriever):
    """Test handling of retrieval failures."""
    # Setup
    query = "Valid query for testing"
    mock_retriever.retrieve.side_effect = Exception("Vector store error")
    
    # Execute and verify
    with pytest.raises(RAGValidationError, match="Retrieval stage failed"):
        rag_pipeline.query(query)


def test_generation_failure_handling(rag_pipeline, mock_retriever, mock_llm_service):
    """Test handling of generation failures."""
    # Setup
    query = "Valid query for testing"
    
    mock_chunks = [
        RetrievedChunk(
            text="Test chunk",
            similarity_score=0.9,
            metadata={"document_id": "doc_1"}
        )
    ]
    mock_retriever.retrieve.return_value = mock_chunks
    mock_llm_service.generate_answer.side_effect = Exception("LLM API error")
    
    # Execute and verify
    with pytest.raises(RAGValidationError, match="Generation stage failed"):
        rag_pipeline.query(query)


def test_processing_time_recorded(rag_pipeline, mock_retriever, mock_llm_service):
    """Test that processing time is recorded correctly."""
    # Setup
    query = "Test query for timing"
    
    mock_chunks = [
        RetrievedChunk(
            text="Test chunk",
            similarity_score=0.9,
            metadata={"document_id": "doc_1"}
        )
    ]
    mock_retriever.retrieve.return_value = mock_chunks
    
    mock_answer = GeneratedAnswer(
        answer="Test answer",
        source_chunks=[],
        model="gemini-2.0-flash-exp",
        tokens_used=10
    )
    mock_llm_service.generate_answer.return_value = mock_answer
    
    # Execute
    response = rag_pipeline.query(query)
    
    # Verify
    assert response.processing_time > 0
    assert response.processing_time < 10  # Should be fast with mocks
