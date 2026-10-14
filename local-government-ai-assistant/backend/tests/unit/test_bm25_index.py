"""
Unit tests for BM25Index.

Tests the BM25 keyword-based search implementation for hybrid retrieval.
"""

import pytest
from app.rag.retrieval.bm25_index import BM25Index
from app.models.data_models import RetrievedChunk


@pytest.fixture
def sample_chunks():
    """Sample Vietnamese chunks for testing."""
    return [
        RetrievedChunk(
            text="Điều 10 quy định về thủ tục đăng ký thường trú",
            similarity_score=0.9,
            metadata={"document_id": "doc1", "chunk_index": 0}
        ),
        RetrievedChunk(
            text="Khoản 3 nêu rõ hồ sơ cần thiết cho CCCD",
            similarity_score=0.85,
            metadata={"document_id": "doc1", "chunk_index": 1}
        ),
        RetrievedChunk(
            text="Quy trình cấp giấy phép kinh doanh tại địa phương",
            similarity_score=0.8,
            metadata={"document_id": "doc2", "chunk_index": 0}
        ),
        RetrievedChunk(
            text="Thủ tục xin giấy phép xây dựng nhà ở",
            similarity_score=0.75,
            metadata={"document_id": "doc2", "chunk_index": 1}
        ),
    ]


def test_bm25_index_initialization():
    """Test BM25Index initializes with correct parameters."""
    index = BM25Index(k1=1.5, b=0.75)
    
    assert index.k1 == 1.5
    assert index.b == 0.75
    assert index.bm25 is None
    assert len(index.corpus_tokens) == 0
    assert len(index.chunk_map) == 0


def test_bm25_index_chunks(sample_chunks):
    """Test building BM25 index from chunks."""
    index = BM25Index()
    index.index_chunks(sample_chunks)
    
    assert index.bm25 is not None
    assert len(index.corpus_tokens) == 4
    assert len(index.chunk_map) == 4
    
    # Check tokenization
    assert len(index.corpus_tokens[0]) > 0
    assert all(token.islower() for tokens in index.corpus_tokens for token in tokens)


def test_bm25_search_exact_term_match(sample_chunks):
    """Test BM25 search finds exact term matches."""
    index = BM25Index()
    index.index_chunks(sample_chunks)
    
    # Search for exact term
    results = index.search("Điều 10", k=5)
    
    assert len(results) > 0
    # First result should contain "Điều 10"
    assert "điều 10" in results[0][0].text.lower()
    # Score should be positive
    assert results[0][1] > 0


def test_bm25_search_keyword_relevance(sample_chunks):
    """Test BM25 ranks by keyword relevance."""
    index = BM25Index()
    index.index_chunks(sample_chunks)
    
    # Search for "thủ tục" - appears in multiple docs
    results = index.search("thủ tục", k=5)
    
    assert len(results) >= 2
    # Results should be sorted by score descending
    for i in range(len(results) - 1):
        assert results[i][1] >= results[i + 1][1]


def test_bm25_search_empty_index():
    """Test BM25 search on empty index returns empty results."""
    index = BM25Index()
    
    results = index.search("test query", k=5)
    
    assert len(results) == 0


def test_bm25_get_stats(sample_chunks):
    """Test get_stats returns correct information."""
    index = BM25Index()
    
    # Before indexing
    stats = index.get_stats()
    assert stats["indexed"] is False
    
    # After indexing
    index.index_chunks(sample_chunks)
    stats = index.get_stats()
    
    assert stats["indexed"] is True
    assert stats["corpus_size"] == 4
    assert stats["avg_doc_length"] > 0
    assert stats["k1"] == 1.5
    assert stats["b"] == 0.75
