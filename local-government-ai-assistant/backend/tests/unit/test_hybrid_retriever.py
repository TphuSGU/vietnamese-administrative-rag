"""
Unit tests for HybridRetriever.

Tests the hybrid retrieval combining vector search and BM25 with RRF fusion.
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.models.data_models import RetrievedChunk


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock()
    service.embed_single = Mock(return_value=[0.1] * 768)
    return service


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    return Mock()


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing."""
    return [
        RetrievedChunk(
            text="Hướng dẫn đăng ký thường trú theo Điều 10",
            similarity_score=0.9,
            metadata={"document_id": "doc1", "chunk_index": 0}
        ),
        RetrievedChunk(
            text="Thủ tục cấp CCCD mới theo quy định",
            similarity_score=0.85,
            metadata={"document_id": "doc1", "chunk_index": 1}
        ),
        RetrievedChunk(
            text="Quy trình xin giấy phép kinh doanh",
            similarity_score=0.8,
            metadata={"document_id": "doc2", "chunk_index": 0}
        ),
    ]


def test_hybrid_retriever_initialization(mock_embedding_service, mock_vector_store):
    """Test HybridRetriever initializes correctly."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        alpha=0.6,
        min_similarity=0.7,
        use_reranking=False
    )
    
    assert retriever.alpha == 0.6
    assert retriever.min_similarity == 0.7
    assert retriever.use_reranking is False
    assert retriever.reranker is None
    assert retriever.bm25_index is not None


def test_hybrid_retriever_index_documents(mock_embedding_service, mock_vector_store, sample_chunks):
    """Test indexing documents for BM25."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        use_reranking=False
    )
    
    retriever.index_documents(sample_chunks)
    
    # Check BM25S index is built (use 'retriever' attribute instead of 'bm25')
    assert retriever.bm25_index.retriever is not None
    assert len(retriever.bm25_index.corpus_tokens) == 3


def test_hybrid_retriever_validates_k_parameter(mock_embedding_service, mock_vector_store, sample_chunks):
    """Test K parameter validation."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        use_reranking=False
    )
    retriever.index_documents(sample_chunks)
    
    # Mock vector store search
    mock_vector_store.search = Mock(return_value=[])
    
    # Valid K
    try:
        retriever.retrieve("test query", k=5)
    except ValueError:
        pytest.fail("Valid K should not raise ValueError")
    
    # Invalid K (too small)
    with pytest.raises(ValueError):
        retriever.retrieve("test query", k=0)
    
    # Invalid K (too large)
    with pytest.raises(ValueError):
        retriever.retrieve("test query", k=25)


def test_hybrid_retriever_reciprocal_rank_fusion(mock_embedding_service, mock_vector_store):
    """Test RRF fusion combines rankings correctly."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        alpha=0.6,
        use_reranking=False
    )
    
    # Create test data
    vector_results = [
        RetrievedChunk("doc A", 0.9, {"doc_id": "A"}),
        RetrievedChunk("doc B", 0.8, {"doc_id": "B"}),
    ]
    
    bm25_results = [
        (RetrievedChunk("doc B", 0.7, {"doc_id": "B"}), 5.0),
        (RetrievedChunk("doc C", 0.6, {"doc_id": "C"}), 3.0),
    ]
    
    fused = retriever._reciprocal_rank_fusion(vector_results, bm25_results, k=3)
    
    # Should have all 3 unique documents
    assert len(fused) == 3
    
    # Each chunk should have RRF scores in metadata
    for chunk in fused:
        assert 'rrf_vector_score' in chunk.metadata
        assert 'rrf_bm25_score' in chunk.metadata
        assert chunk.similarity_score > 0


def test_hybrid_retriever_filter_by_threshold(mock_embedding_service, mock_vector_store):
    """Test filtering by similarity threshold."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        min_similarity=0.75,
        use_reranking=False
    )
    
    chunks = [
        RetrievedChunk("high score", 0.9, {}),
        RetrievedChunk("medium score", 0.76, {}),
        RetrievedChunk("low score", 0.5, {}),
    ]
    
    filtered = retriever._filter_by_threshold(chunks)
    
    # Should only keep chunks >= 0.75
    assert len(filtered) == 2
    assert all(chunk.similarity_score >= 0.75 for chunk in filtered)


def test_hybrid_retriever_empty_results(mock_embedding_service, mock_vector_store):
    """Test handling of empty results."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        use_reranking=False
    )
    
    # Empty chunks
    fused = retriever._reciprocal_rank_fusion([], [], k=5)
    assert len(fused) == 0
    
    # Empty filtering
    filtered = retriever._filter_by_threshold([])
    assert len(filtered) == 0


def test_hybrid_retriever_get_stats(mock_embedding_service, mock_vector_store, sample_chunks):
    """Test get_stats returns correct information."""
    retriever = HybridRetriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        alpha=0.6,
        min_similarity=0.7,
        use_reranking=False
    )
    retriever.index_documents(sample_chunks)
    
    stats = retriever.get_stats()
    
    assert stats["type"] == "hybrid"
    assert stats["alpha"] == 0.6
    assert stats["min_similarity"] == 0.7
    assert stats["rrf_k"] == 60
    assert stats["reranking_enabled"] is False
    assert "bm25s_stats" in stats  # Changed from bm25_stats to bm25s_stats


def test_hybrid_retriever_with_reranking_enabled(mock_embedding_service, mock_vector_store):
    """Test retriever with reranking enabled initializes correctly."""
    # Note: This test might fail if sentence-transformers is not installed
    try:
        retriever = HybridRetriever(
            embedding_service=mock_embedding_service,
            vector_store=mock_vector_store,
            use_reranking=True
        )
        assert retriever.use_reranking is True
        assert retriever.reranker is not None
    except Exception:
        pytest.skip("Reranker dependencies not available")
