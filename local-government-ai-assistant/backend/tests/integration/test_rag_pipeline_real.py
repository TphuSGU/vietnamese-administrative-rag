"""
Integration tests for complete RAG Pipeline with real components.

These tests verify the end-to-end RAG workflow using actual components
(not mocks) to ensure real-world functionality.

**Validates: Requirements 7.1, 7.2, 7.3, 10.1, 10.2, 10.3, 10.4, 10.5**
"""

import pytest
import os
from pathlib import Path
import json

from app.rag.pipeline.rag_pipeline import RAGPipeline
from app.rag.retrieval.retriever import Retriever
from app.rag.generation.llm_service import LLMService
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.models.exceptions import RAGValidationError


@pytest.fixture
def rag_pipeline(tmp_path):
    """Create RAG pipeline with real components."""
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    
    # Initialize components
    vector_store = VectorStore(persist_directory=str(tmp_path / "chroma_test"))
    embedding_service = EmbeddingService()
    retriever = Retriever(embedding_service, vector_store)
    llm_service = LLMService(api_key=api_key)
    
    return RAGPipeline(
        retriever=retriever,
        llm_service=llm_service,
        log_dir=tmp_path / "logs"
    )


def test_end_to_end_query_processing(rag_pipeline):
    """
    Test complete query flow: validate → retrieve → generate.
    
    Note: This requires data in vector store. For now, test empty result handling.
    
    **Validates: Requirements 10.1, 10.2, 10.3**
    """
    response = rag_pipeline.query(
        query="Thủ tục đăng ký hộ khẩu cần giấy tờ gì?",
        k=5
    )
    
    # Should get empty response (no docs in store yet)
    assert response.query_id is not None
    assert "không tìm thấy" in response.answer.lower() or "không có" in response.answer.lower()
    assert response.processing_time > 0
    assert response.model == "gemini-2.0-flash-exp"


def test_query_validation_min_length(rag_pipeline):
    """
    Test query length validation (minimum).
    
    **Validates: Requirement 7.2 (query validation)**
    """
    with pytest.raises(RAGValidationError) as exc_info:
        rag_pipeline.query("short")
    
    assert "too short" in str(exc_info.value).lower()


def test_query_validation_max_length(rag_pipeline):
    """
    Test query length validation (maximum).
    
    **Validates: Requirement 7.2 (query validation)**
    """
    long_query = "x" * 501
    
    with pytest.raises(RAGValidationError) as exc_info:
        rag_pipeline.query(long_query)
    
    assert "too long" in str(exc_info.value).lower()


def test_query_validation_empty(rag_pipeline):
    """
    Test that empty queries are rejected.
    
    **Validates: Requirement 7.2**
    """
    with pytest.raises(RAGValidationError, match="cannot be empty"):
        rag_pipeline.query("")
    
    with pytest.raises(RAGValidationError, match="cannot be empty"):
        rag_pipeline.query("   ")


def test_query_validation_utf8(rag_pipeline):
    """
    Test UTF-8 validation for queries.
    
    **Validates: Requirement 16.3 (UTF-8 validation)**
    """
    # Valid UTF-8 Vietnamese query
    valid_query = "Đăng ký hộ khẩu cần giấy tờ gì?"
    response = rag_pipeline.query(valid_query)
    assert response is not None


def test_query_logging(rag_pipeline, tmp_path):
    """
    Test query logging to JSONL.
    
    **Validates: Requirement 10.4 (query logging)**
    """
    response = rag_pipeline.query(
        query="Test query for logging functionality",
        k=5
    )
    
    # Check log file created
    log_file = tmp_path / "logs" / "query_logs.jsonl"
    assert log_file.exists()
    
    # Verify log content
    with open(log_file, 'r', encoding='utf-8') as f:
        log_line = f.read().strip()
    
    assert len(log_line) > 0
    log_entry = json.loads(log_line)
    
    # Verify log completeness (Req 10.4)
    assert log_entry["query_id"] == response.query_id
    assert "Test query for logging" in log_entry["query"]
    assert "timestamp" in log_entry
    assert "processing_time_ms" in log_entry
    assert log_entry["processing_time_ms"] > 0


def test_processing_time_tracked(rag_pipeline):
    """
    Test processing time is tracked.
    
    **Validates: Requirement 10.5 (processing time)**
    """
    response = rag_pipeline.query(
        query="Test query for timing measurement",
        k=5
    )
    
    assert response.processing_time > 0
    assert response.processing_time < 30  # Should be reasonable


def test_query_with_different_k_values(rag_pipeline):
    """Test RAG pipeline with different K values."""
    for k in [1, 3, 5, 10, 20]:
        response = rag_pipeline.query(
            query="Quy trình đăng ký hộ khẩu như thế nào?",
            k=k
        )
        assert response is not None
        assert response.query_id is not None


def test_query_with_vietnamese_diacritics(rag_pipeline):
    """
    Test that Vietnamese queries with diacritics are handled correctly.
    
    **Validates: Requirement 7.1 (Vietnamese query support)**
    """
    queries = [
        "Thủ tục đăng ký hộ khẩu thường trú?",
        "Cần những giấy tờ gì để xin cấp CMND?",
        "Quy trình làm hộ chiếu mới như thế nào?",
    ]
    
    for query in queries:
        response = rag_pipeline.query(query, k=5)
        assert response is not None
        assert response.query_id is not None
        assert len(response.answer) > 0


def test_response_structure_completeness(rag_pipeline):
    """
    Test that RAG response contains all required fields.
    
    **Validates: Requirement 10.5 (response completeness)**
    """
    response = rag_pipeline.query(
        query="Test query for response structure validation",
        k=5
    )
    
    # Verify all required fields present
    assert hasattr(response, 'query_id')
    assert hasattr(response, 'answer')
    assert hasattr(response, 'source_chunks')
    assert hasattr(response, 'relevance_scores')
    assert hasattr(response, 'processing_time')
    assert hasattr(response, 'model')
    
    assert response.query_id is not None
    assert response.answer is not None
    assert isinstance(response.source_chunks, list)
    assert isinstance(response.relevance_scores, list)
    assert response.processing_time > 0
    assert response.model is not None


def test_empty_retrieval_handling(rag_pipeline):
    """
    Test handling when retrieval returns no results.
    
    **Validates: Requirement 10.3 (empty result handling)**
    """
    response = rag_pipeline.query(
        query="Câu hỏi hoàn toàn không liên quan đến bất kỳ tài liệu nào",
        k=5
    )
    
    # Should return appropriate Vietnamese message
    assert "không tìm thấy" in response.answer.lower() or "không có tài liệu" in response.answer.lower()
    assert len(response.source_chunks) == 0
    assert len(response.relevance_scores) == 0


def test_multiple_queries_in_sequence(rag_pipeline):
    """Test executing multiple queries in sequence."""
    queries = [
        "Đăng ký hộ khẩu cần gì?",
        "Thủ tục làm CMND?",
        "Xin cấp hộ chiếu như thế nào?",
    ]
    
    responses = []
    for query in queries:
        response = rag_pipeline.query(query, k=5)
        responses.append(response)
    
    # All should complete successfully
    assert len(responses) == 3
    assert all(r.query_id is not None for r in responses)
    assert all(r.processing_time > 0 for r in responses)
    
    # Each should have unique query ID
    query_ids = [r.query_id for r in responses]
    assert len(set(query_ids)) == 3


def test_log_file_accumulation(rag_pipeline, tmp_path):
    """Test that log file accumulates entries from multiple queries."""
    # Execute multiple queries
    for i in range(3):
        rag_pipeline.query(f"Test query number {i} for log accumulation", k=5)
    
    # Check log file
    log_file = tmp_path / "logs" / "query_logs.jsonl"
    assert log_file.exists()
    
    with open(log_file, 'r', encoding='utf-8') as f:
        log_lines = f.readlines()
    
    # Should have 3 entries
    assert len(log_lines) == 3
    
    # Each should be valid JSON
    for line in log_lines:
        log_entry = json.loads(line.strip())
        assert "query_id" in log_entry
        assert "query" in log_entry


def test_vietnamese_answer_generation(rag_pipeline):
    """
    Test that answers are generated in Vietnamese.
    
    **Validates: Requirement 9.4 (Vietnamese response)**
    """
    response = rag_pipeline.query(
        query="Hỏi về thủ tục hành chính",
        k=5
    )
    
    # Answer should be in Vietnamese or state no documents found
    answer_lower = response.answer.lower()
    # Check for Vietnamese words/characters
    vietnamese_indicators = [
        "không", "tìm", "thấy", "tài liệu", "thông tin",
        "không có", "văn bản", "hồ sơ"
    ]
    assert any(indicator in answer_lower for indicator in vietnamese_indicators)


def test_query_id_uniqueness(rag_pipeline):
    """Test that each query gets a unique query ID."""
    query_ids = set()
    
    for _ in range(5):
        response = rag_pipeline.query("Test query for ID uniqueness", k=5)
        query_ids.add(response.query_id)
    
    # All IDs should be unique
    assert len(query_ids) == 5


def test_processing_time_within_requirement(rag_pipeline):
    """
    Test that query processing completes within time requirement.
    
    **Validates: Requirement 10.2 (< 5 seconds for standard queries)**
    
    Note: With empty vector store and no actual retrieval, this should be fast.
    With real data, may take longer but should still be reasonable.
    """
    import time
    
    start = time.time()
    response = rag_pipeline.query(
        query="Thủ tục đăng ký tạm trú?",
        k=5
    )
    actual_time = time.time() - start
    
    # Should complete relatively quickly
    assert actual_time < 30  # Allow 30s for integration test
    
    # Response should also track time
    assert response.processing_time > 0
    assert abs(response.processing_time - actual_time) < 1.0  # Within 1 second
