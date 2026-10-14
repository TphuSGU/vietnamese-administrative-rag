"""
Tests for Chat API endpoints.

Tests:
- POST /api/v1/chat/query - RAG query endpoint
- GET /api/v1/chat/health - Health check endpoint
- GET /api/v1/chat/stats - Statistics endpoint
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from app.main import app
from app.models.data_models import RAGResponse, ChunkReference, RetrievedChunk
from app.models.exceptions import RAGValidationError, RAGException
from app.core.dependencies import (
    get_hybrid_pipeline,
    get_embedding_service,
    get_vector_store,
    get_llm_service,
    get_output_validator
)
from datetime import datetime
import uuid


# ============================================================================
# Test Client Setup
# ============================================================================

client = TestClient(app)


# ============================================================================
# Fixtures for Cleanup
# ============================================================================

@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# ============================================================================
# Mock Data
# ============================================================================

def create_mock_rag_response(
    query_id: str = None,
    answer: str = "Đây là câu trả lời mẫu từ tài liệu.",
    num_sources: int = 3
) -> RAGResponse:
    """Create a mock RAG response for testing."""
    if query_id is None:
        query_id = str(uuid.uuid4())
    
    source_chunks = [
        ChunkReference(
            document_id=f"doc_{i}",
            text=f"Nội dung tài liệu {i}...",
            similarity_score=0.9 - (i * 0.05),
            chunk_index=i
        )
        for i in range(num_sources)
    ]
    
    return RAGResponse(
        query_id=query_id,
        answer=answer,
        source_chunks=source_chunks,
        relevance_scores=[0.9, 0.85, 0.80],
        processing_time=1.234,
        model="gemini-2.0-flash-exp",
        timestamp=datetime.utcnow()
    )


def create_mock_retrieved_chunks(num: int = 3) -> list:
    """Create mock retrieved chunks."""
    return [
        RetrievedChunk(
            text=f"Chunk {i} content",
            similarity_score=0.9 - (i * 0.05),
            metadata={
                "document_id": f"doc_{i}",
                "chunk_index": i,
                "heading_context": f"Heading {i}"
            }
        )
        for i in range(num)
    ]


# ============================================================================
# Query Endpoint Tests
# ============================================================================

def test_query_endpoint_success():
    """Test successful RAG query."""
    # Setup mock
    mock_pipeline = Mock()
    mock_response = create_mock_rag_response()
    mock_pipeline.query.return_value = mock_response
    
    # Override dependency
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    try:
        # Make request
        response = client.post(
            "/api/v1/chat/query",
            json={
                "query": "Điều 10 quy định gì về hộ khẩu?",
                "k": 5
            }
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert "query_id" in data
        assert "answer" in data
        assert "source_chunks" in data
        assert "relevance_scores" in data
        assert "processing_time" in data
        assert "model" in data
        
        assert data["answer"] == mock_response.answer
        assert len(data["source_chunks"]) == 3
        assert data["model"] == "gemini-2.0-flash-exp"
        
        # Verify pipeline was called correctly
        mock_pipeline.query.assert_called_once()
        call_args = mock_pipeline.query.call_args
        assert call_args[1]["query"] == "Điều 10 quy định gì về hộ khẩu?"
        assert call_args[1]["k"] == 5
    finally:
        # Clean up
        app.dependency_overrides.clear()


def test_query_endpoint_validation_error():
    """Test query with validation error."""
    # Setup mock to raise validation error
    mock_pipeline = Mock()
    mock_pipeline.query.side_effect = RAGValidationError("Query too short")
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    # Make request
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10 quy định gì về hộ khẩu?",
            "k": 5
        }
    )
    
    # Assertions
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Câu hỏi không hợp lệ" in data["detail"]


def test_query_endpoint_empty_query():
    """Test query with empty string."""
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "   ",  # Only whitespace
            "k": 5
        }
    )
    
    # Should fail validation before reaching pipeline
    assert response.status_code == 422  # Validation error


def test_query_endpoint_query_too_short():
    """Test query that's too short."""
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10",  # Less than 10 chars
            "k": 5
        }
    )
    
    # Should fail Pydantic validation
    assert response.status_code == 422


def test_query_endpoint_query_too_long():
    """Test query that's too long."""
    long_query = "A" * 501  # Exceeds 500 char limit
    
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": long_query,
            "k": 5
        }
    )
    
    # Should fail Pydantic validation
    assert response.status_code == 422


def test_query_endpoint_invalid_k_too_small():
    """Test query with k=0 (invalid)."""
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10 quy định gì về hộ khẩu?",
            "k": 0
        }
    )
    
    # Should fail validation
    assert response.status_code == 422


def test_query_endpoint_invalid_k_too_large():
    """Test query with k=25 (exceeds limit)."""
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10 quy định gì về hộ khẩu?",
            "k": 25
        }
    )
    
    # Should fail validation
    assert response.status_code == 422


def test_query_endpoint_with_different_k_values():
    """Test query with various valid k values."""
    mock_pipeline = Mock()
    mock_pipeline.query.return_value = create_mock_rag_response()
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    for k in [1, 5, 10, 20]:
        response = client.post(
            "/api/v1/chat/query",
            json={
                "query": "Điều 10 quy định gì về hộ khẩu?",
                "k": k
            }
        )
        
        assert response.status_code == 200
        
        # Verify k was passed correctly
        call_args = mock_pipeline.query.call_args
        assert call_args[1]["k"] == k


def test_query_endpoint_rag_exception():
    """Test query with RAG pipeline exception."""
    mock_pipeline = Mock()
    mock_pipeline.query.side_effect = RAGException("Retrieval failed")
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10 quy định gì về hộ khẩu?",
            "k": 5
        }
    )
    
    # Should return 500 with error message
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Lỗi xử lý câu hỏi" in data["detail"]


def test_query_endpoint_unexpected_error():
    """Test query with unexpected exception."""
    mock_pipeline = Mock()
    mock_pipeline.query.side_effect = RuntimeError("Unexpected error")
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Điều 10 quy định gì về hộ khẩu?",
            "k": 5
        }
    )
    
    # Should return 500
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data


# ============================================================================
# Health Endpoint Tests
# ============================================================================

def test_health_endpoint_all_healthy():
    """Test health check when all components are healthy."""
    # Setup mocks
    mock_embedding = Mock()
    mock_embedding.health_check.return_value = True
    mock_embedding.MODEL_NAME = "vietnamese-bi-encoder"
    mock_embedding.EMBEDDING_DIM = 768
    
    mock_vector = Mock()
    mock_vector.health_check.return_value = True
    mock_vector.get_collection_stats.return_value = {
        "name": "documents",
        "count": 1500
    }
    
    mock_llm = Mock()
    mock_llm.MODEL_NAME = "gemini-2.0-flash-exp"
    
    mock_validator = Mock()
    mock_validator.min_evidence_ratio = 0.4
    mock_validator.strict_mode = False
    
    # Override dependencies
    app.dependency_overrides[get_embedding_service] = lambda: mock_embedding
    app.dependency_overrides[get_vector_store] = lambda: mock_vector
    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    app.dependency_overrides[get_output_validator] = lambda: mock_validator
    
    # Make request
    response = client.get("/api/v1/chat/health")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "components" in data
    
    # Check all components
    assert "vector_store" in data["components"]
    assert data["components"]["vector_store"]["status"] == "healthy"
    assert data["components"]["vector_store"]["count"] == 1500
    
    assert "embedding_service" in data["components"]
    assert data["components"]["embedding_service"]["status"] == "healthy"
    
    assert "llm_service" in data["components"]
    assert data["components"]["llm_service"]["status"] == "healthy"
    
    assert "validator" in data["components"]
    assert data["components"]["validator"]["status"] == "healthy"


def test_health_endpoint_degraded():
    """Test health check when some non-critical components fail."""
    # Setup mocks - LLM service will cause an error during check
    mock_embedding = Mock()
    mock_embedding.health_check.return_value = True
    mock_embedding.MODEL_NAME = "vietnamese-bi-encoder"
    mock_embedding.EMBEDDING_DIM = 768
    
    mock_vector = Mock()
    mock_vector.health_check.return_value = True
    mock_vector.get_collection_stats.return_value = {
        "name": "documents",
        "count": 1500
    }
    
    # LLM service MODEL_NAME raises exception (simulates error accessing attribute)
    mock_llm = Mock()
    type(mock_llm).MODEL_NAME = PropertyMock(side_effect=Exception("LLM error"))
    
    mock_validator = Mock()
    mock_validator.min_evidence_ratio = 0.4
    mock_validator.strict_mode = False
    
    # Override dependencies
    app.dependency_overrides[get_embedding_service] = lambda: mock_embedding
    app.dependency_overrides[get_vector_store] = lambda: mock_vector
    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    app.dependency_overrides[get_output_validator] = lambda: mock_validator
    
    # Make request
    response = client.get("/api/v1/chat/health")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    # LLM service has error, system is degraded
    assert data["status"] == "degraded"
    assert data["components"]["llm_service"]["status"] == "unhealthy"


def test_health_endpoint_unhealthy():
    """Test health check when critical components fail."""
    # Setup mocks - embedding service fails
    mock_embedding = Mock()
    mock_embedding.health_check.return_value = False
    mock_embedding.MODEL_NAME = "vietnamese-bi-encoder"
    mock_embedding.EMBEDDING_DIM = 768
    
    mock_vector = Mock()
    mock_vector.health_check.return_value = True
    mock_vector.get_collection_stats.return_value = {"name": "documents", "count": 0}
    
    mock_llm = Mock()
    mock_llm.MODEL_NAME = "gemini-2.0-flash-exp"
    
    mock_validator = Mock()
    mock_validator.min_evidence_ratio = 0.4
    mock_validator.strict_mode = False
    
    # Override dependencies
    app.dependency_overrides[get_embedding_service] = lambda: mock_embedding
    app.dependency_overrides[get_vector_store] = lambda: mock_vector
    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    app.dependency_overrides[get_output_validator] = lambda: mock_validator
    
    # Make request
    response = client.get("/api/v1/chat/health")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    # Embedding service unhealthy = overall unhealthy
    assert data["status"] == "unhealthy"
    assert data["components"]["embedding_service"]["status"] == "unhealthy"


# ============================================================================
# Stats Endpoint Tests
# ============================================================================

def test_stats_endpoint():
    """Test stats endpoint returns pipeline configuration."""
    # Setup mock
    mock_pipeline = Mock()
    mock_pipeline.get_stats.return_value = {
        "pipeline_type": "hybrid",
        "retriever_stats": {
            "type": "hybrid",
            "alpha": 0.6,
            "min_similarity": 0.7,
            "rrf_k": 60,
            "reranking_enabled": True,
            "bm25_stats": {"indexed_chunks": 1000}
        },
        "validator_enabled": True,
        "max_retries": 1
    }
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    # Make request
    response = client.get("/api/v1/chat/stats")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    assert data["pipeline_type"] == "hybrid"
    assert "retriever_stats" in data
    assert data["retriever_stats"]["type"] == "hybrid"
    assert data["retriever_stats"]["alpha"] == 0.6
    assert data["validator_enabled"] is True
    assert data["max_retries"] == 1


def test_stats_endpoint_error():
    """Test stats endpoint when pipeline throws error."""
    # Setup mock to throw exception
    mock_pipeline = Mock()
    mock_pipeline.get_stats.side_effect = Exception("Stats error")
    
    app.dependency_overrides[get_hybrid_pipeline] = lambda: mock_pipeline
    
    # Make request
    response = client.get("/api/v1/chat/stats")
    
    # Assertions
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data


# ============================================================================
# Root Endpoint Test
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns API info."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert data["version"] == "1.0.0"
