"""Integration tests for Retriever component."""

import pytest
import numpy as np
from unittest.mock import Mock

from app.rag.retrieval.retriever import Retriever
from app.models.data_models import SearchResult, RetrievedChunk


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock()
    service.embed_single.return_value = np.random.rand(768)
    return service


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = Mock()
    return store


@pytest.fixture
def retriever(mock_embedding_service, mock_vector_store):
    """Create Retriever instance."""
    return Retriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store
    )


def test_retrieve_with_default_k(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieval with default K=5."""
    # Setup
    query = "Thủ tục đăng ký hộ khẩu"
    
    # Mock search results
    mock_results = [
        SearchResult(
            chunk_id=f"doc_1_{i}",
            text=f"Chunk {i}",
            metadata={"document_id": "doc_1", "heading_context": "Heading"},
            similarity_score=0.9 - i * 0.1,
            distance=0.1 + i * 0.1
        )
        for i in range(5)
    ]
    mock_vector_store.search.return_value = mock_results
    
    # Execute
    results = retriever.retrieve(query)
    
    # Verify
    assert len(results) == 5
    assert all(isinstance(r, RetrievedChunk) for r in results)
    assert results[0].similarity_score > results[-1].similarity_score
    mock_embedding_service.embed_single.assert_called_once_with(query)
    mock_vector_store.search.assert_called_once()


def test_retrieve_with_custom_k(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieval with custom K=10."""
    # Setup
    query = "Hướng dẫn đăng ký kinh doanh"
    k = 10
    
    # Mock search results
    mock_results = [
        SearchResult(
            chunk_id=f"doc_1_{i}",
            text=f"Chunk {i}",
            metadata={"document_id": "doc_1"},
            similarity_score=0.95 - i * 0.05,
            distance=0.05 + i * 0.05
        )
        for i in range(10)
    ]
    mock_vector_store.search.return_value = mock_results
    
    # Execute
    results = retriever.retrieve(query, k=k)
    
    # Verify
    assert len(results) == 10
    _, kwargs = mock_vector_store.search.call_args
    assert kwargs.get('k') == 10 or (len(args := mock_vector_store.search.call_args[0]) > 1 and args[1] == 10)


def test_retrieve_validates_k_bounds(retriever):
    """Test that K validation rejects out-of-bounds values."""
    query = "Test query"
    
    # Test K < MIN_K
    with pytest.raises(ValueError, match="K must be between"):
        retriever.retrieve(query, k=0)
    
    # Test K > MAX_K
    with pytest.raises(ValueError, match="K must be between"):
        retriever.retrieve(query, k=21)


def test_retrieve_handles_empty_results(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieval when no results found."""
    # Setup
    query = "Không tìm thấy"
    mock_vector_store.search.return_value = []
    
    # Execute
    results = retriever.retrieve(query)
    
    # Verify
    assert len(results) == 0
    assert results == []


def test_retrieve_preserves_metadata(retriever, mock_embedding_service, mock_vector_store):
    """Test that retrieval preserves all metadata."""
    # Setup
    query = "Test query"
    
    mock_results = [
        SearchResult(
            chunk_id="doc_1_0",
            text="Test chunk",
            metadata={
                "document_id": "doc_1",
                "heading_context": "Section 1",
                "chunk_index": 0,
                "page": 5
            },
            similarity_score=0.95,
            distance=0.05
        )
    ]
    mock_vector_store.search.return_value = mock_results
    
    # Execute
    results = retriever.retrieve(query, k=1)
    
    # Verify
    assert len(results) == 1
    chunk = results[0]
    assert chunk.document_id == "doc_1"
    assert chunk.heading_context == "Section 1"
    assert chunk.chunk_index == 0
    assert chunk.metadata["page"] == 5
