"""
Integration tests for BM25SIndex.

Tests the BM25S keyword-based search implementation with persistence support.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from app.rag.retrieval.bm25s_index import BM25SIndex
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
        RetrievedChunk(
            text="Hướng dẫn về CMND và CCCD cho công dân",
            similarity_score=0.7,
            metadata={"document_id": "doc3", "chunk_index": 0}
        ),
    ]


@pytest.fixture
def temp_persist_dir():
    """Create a temporary directory for persistence tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_bm25s_index_initialization():
    """Test BM25SIndex initializes with correct parameters."""
    index = BM25SIndex(k1=1.5, b=0.75)
    
    assert index.k1 == 1.5
    assert index.b == 0.75
    assert index.retriever is None
    assert len(index.corpus_tokens) == 0
    assert len(index.chunk_map) == 0


def test_bm25s_index_initialization_with_persistence(temp_persist_dir):
    """Test BM25SIndex initializes with persistence directory."""
    index = BM25SIndex(k1=1.5, b=0.75, persist_dir=temp_persist_dir)
    
    assert index.persist_dir == temp_persist_dir
    assert index.k1 == 1.5
    assert index.b == 0.75


def test_bm25s_tokenization():
    """Test Vietnamese tokenization handles punctuation and diacritics."""
    index = BM25SIndex()
    
    # Test Vietnamese text with punctuation
    text = "Điều 10: Quyền công dân"
    tokens = index._tokenize(text)
    
    assert "điều" in tokens
    assert "10" in tokens
    assert "quyền" in tokens
    assert "công" in tokens
    assert "dân" in tokens
    # Punctuation should be removed
    assert ":" not in tokens
    # All lowercase
    assert all(token.islower() or token.isdigit() for token in tokens)


def test_bm25s_index_chunks(sample_chunks):
    """Test building BM25S index from chunks."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    assert index.retriever is not None
    assert len(index.corpus_tokens) == 5
    assert len(index.chunk_map) == 5
    
    # Check tokenization
    assert len(index.corpus_tokens[0]) > 0
    assert all(token.islower() or token.isdigit() 
               for tokens in index.corpus_tokens 
               for token in tokens)


def test_bm25s_search_exact_term_match(sample_chunks):
    """Test BM25S search finds exact term matches."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Search for exact term
    results = index.search("Điều 10", k=5)
    
    assert len(results) > 0
    # First result should contain "Điều 10"
    assert "điều 10" in results[0][0].text.lower()
    # Score should be positive
    assert results[0][1] > 0


def test_bm25s_search_keyword_relevance(sample_chunks):
    """Test BM25S ranks by keyword relevance."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Search for "thủ tục" - appears in multiple docs
    results = index.search("thủ tục", k=5)
    
    assert len(results) >= 2
    # Results should be sorted by score descending
    for i in range(len(results) - 1):
        assert results[i][1] >= results[i + 1][1]


def test_bm25s_search_multiple_terms(sample_chunks):
    """Test BM25S search with multiple terms."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Search for multiple terms
    results = index.search("CCCD công dân", k=5)
    
    assert len(results) > 0
    # Should find documents containing these terms
    top_text = results[0][0].text.lower()
    assert "cccd" in top_text or "công dân" in top_text


def test_bm25s_search_empty_index():
    """Test BM25S search on empty index returns empty results."""
    index = BM25SIndex()
    
    results = index.search("test query", k=5)
    
    assert len(results) == 0


def test_bm25s_search_no_results():
    """Test BM25S search returns empty when no relevant documents."""
    index = BM25SIndex()
    chunks = [
        RetrievedChunk(
            text="Completely unrelated content",
            similarity_score=0.5,
            metadata={}
        )
    ]
    index.index_chunks(chunks)
    
    # Search for something not in corpus
    results = index.search("xyz123 nonexistent term", k=5)
    
    # Should return empty or very low scores
    assert len(results) == 0 or all(score < 0.01 for _, score in results)


def test_bm25s_persistence_save_load(sample_chunks, temp_persist_dir):
    """Test BM25S index can be saved and loaded from disk."""
    # Create and index
    index1 = BM25SIndex(persist_dir=temp_persist_dir)
    index1.index_chunks(sample_chunks)
    
    # Verify files were created
    assert (temp_persist_dir / "corpus_tokens.pkl").exists()
    assert (temp_persist_dir / "chunk_map.pkl").exists()
    
    # Create new index and load
    index2 = BM25SIndex(persist_dir=temp_persist_dir)
    
    # Should auto-load on initialization
    assert index2.retriever is not None
    assert len(index2.corpus_tokens) == 5
    assert len(index2.chunk_map) == 5
    
    # Search should work the same
    results1 = index1.search("Điều 10", k=3)
    results2 = index2.search("Điều 10", k=3)
    
    assert len(results1) == len(results2)
    assert results1[0][0].text == results2[0][0].text


def test_bm25s_persistence_manual_save_load(sample_chunks, temp_persist_dir):
    """Test manual save and load operations."""
    # Create index without auto-persistence
    index1 = BM25SIndex()
    index1.index_chunks(sample_chunks)
    
    # Manual save
    save_path = temp_persist_dir / "manual_save"
    success = index1.save_index(save_path)
    assert success is True
    
    # Manual load
    index2 = BM25SIndex()
    load_success = index2.load_index(save_path)
    assert load_success is True
    
    # Verify loaded index works
    results = index2.search("giấy phép", k=3)
    assert len(results) > 0


def test_bm25s_persistence_load_nonexistent(temp_persist_dir):
    """Test loading from nonexistent directory fails gracefully."""
    nonexistent_path = temp_persist_dir / "nonexistent"
    
    index = BM25SIndex()
    success = index.load_index(nonexistent_path)
    
    assert success is False
    assert index.retriever is None


def test_bm25s_get_stats(sample_chunks):
    """Test get_stats returns correct information."""
    index = BM25SIndex()
    
    # Before indexing
    stats = index.get_stats()
    assert stats["indexed"] is False
    
    # After indexing
    index.index_chunks(sample_chunks)
    stats = index.get_stats()
    
    assert stats["indexed"] is True
    assert stats["corpus_size"] == 5
    assert stats["avg_doc_length"] > 0
    assert stats["k1"] == 1.5
    assert stats["b"] == 0.75


def test_bm25s_get_stats_with_persistence(sample_chunks, temp_persist_dir):
    """Test get_stats includes persistence information."""
    index = BM25SIndex(persist_dir=temp_persist_dir)
    index.index_chunks(sample_chunks)
    
    stats = index.get_stats()
    
    assert stats["indexed"] is True
    assert stats["persist_dir"] == str(temp_persist_dir)


def test_bm25s_large_k_parameter(sample_chunks):
    """Test search with k larger than corpus size."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Request more results than available
    results = index.search("thủ tục", k=100)
    
    # Should return at most corpus_size results
    assert len(results) <= len(sample_chunks)


def test_bm25s_vietnamese_diacritics_preserved(sample_chunks):
    """Test Vietnamese diacritics are preserved in search."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Search with diacritics
    results_with = index.search("thủ tục", k=5)
    
    assert len(results_with) > 0
    # Should match "thủ tục" in documents
    assert any("thủ tục" in result[0].text.lower() for result in results_with)


def test_bm25s_case_insensitive_search(sample_chunks):
    """Test search is case-insensitive."""
    index = BM25SIndex()
    index.index_chunks(sample_chunks)
    
    # Search with different cases
    results_lower = index.search("điều 10", k=3)
    results_upper = index.search("ĐIỀU 10", k=3)
    results_mixed = index.search("Điều 10", k=3)
    
    # All should return same results
    assert len(results_lower) > 0
    assert len(results_upper) > 0
    assert len(results_mixed) > 0
    assert results_lower[0][0].text == results_upper[0][0].text
    assert results_lower[0][0].text == results_mixed[0][0].text
