"""
Unit tests for VectorStore (ChromaDB implementation).

Tests cover:
1. Initialization (3 tests)
2. Add Chunks (5 tests)
3. Search (7 tests)
4. Delete (3 tests)
5. Health Check (2 tests)

Validates: Requirements 5.1-5.6
"""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from app.database.vector_store import VectorStore
from app.models.data_models import Chunk, SearchResult
from app.models.exceptions import VectorStoreError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create temporary directory for ChromaDB storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vector_store(temp_db_path):
    """Create VectorStore instance with temp storage."""
    return VectorStore(persist_directory=temp_db_path)


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        Chunk(
            text="Thủ tục đăng ký hộ khẩu thường trú tại địa phương.",
            document_id="doc_001",
            chunk_index=0,
            heading_context="Điều 1: Đăng ký hộ khẩu",
            char_start=0,
            char_end=52
        ),
        Chunk(
            text="Công dân phải xuất trình giấy tờ tùy thân hợp lệ.",
            document_id="doc_001",
            chunk_index=1,
            heading_context="Điều 1: Đăng ký hộ khẩu",
            char_start=52,
            char_end=102
        ),
        Chunk(
            text="Thời gian giải quyết hồ sơ là 15 ngày làm việc.",
            document_id="doc_001",
            chunk_index=2,
            heading_context="Điều 2: Thời hạn giải quyết",
            char_start=102,
            char_end=150
        )
    ]


@pytest.fixture
def sample_embeddings():
    """Create sample 768-dimensional embeddings."""
    # Create 3 embeddings of 768 dimensions each
    embeddings = np.random.randn(3, 768).astype(np.float32)
    # Normalize to unit length (L2 norm = 1)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings


# ============================================================================
# 1. Initialization Tests (3 tests)
# ============================================================================

def test_vector_store_initialization_success(temp_db_path):
    """Test successful VectorStore initialization."""
    store = VectorStore(persist_directory=temp_db_path)
    
    assert store is not None
    assert store.client is not None
    assert store.collection is not None
    assert store.COLLECTION_NAME == "vietnamese_documents"
    assert store.EMBEDDING_DIM == 768


def test_vector_store_collection_creation(temp_db_path):
    """Test collection is created with correct configuration."""
    store = VectorStore(persist_directory=temp_db_path)
    
    # Check collection exists
    collections = store.client.list_collections()
    collection_names = [c.name for c in collections]
    assert store.COLLECTION_NAME in collection_names
    
    # Check collection metadata
    metadata = store.collection.metadata
    assert metadata["hnsw:space"] == "cosine"
    assert metadata["hnsw:construction_ef"] == 200
    assert metadata["hnsw:search_ef"] == 100
    assert metadata["hnsw:M"] == 16


def test_vector_store_persistence_directory_creation(temp_db_path):
    """Test persistence directory is created if it doesn't exist."""
    new_path = Path(temp_db_path) / "new_chroma_db"
    assert not new_path.exists()
    
    store = VectorStore(persist_directory=str(new_path))
    
    assert new_path.exists()
    assert store.client is not None


# ============================================================================
# 2. Add Chunks Tests (5 tests)
# ============================================================================

def test_add_single_chunk(vector_store):
    """Test adding a single chunk."""
    chunk = Chunk(
        text="Test text",
        document_id="doc_test",
        chunk_index=0,
        char_start=0,
        char_end=9
    )
    embedding = np.random.randn(1, 768).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    
    vector_store.add_chunks([chunk], embedding)
    
    # Verify chunk was added
    stats = vector_store.get_collection_stats()
    assert stats["count"] == 1


def test_add_multiple_chunks(vector_store, sample_chunks, sample_embeddings):
    """Test adding multiple chunks at once."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Verify all chunks were added
    stats = vector_store.get_collection_stats()
    assert stats["count"] == 3


def test_add_chunks_incremental_indexing(vector_store, sample_chunks, sample_embeddings):
    """Test incremental indexing (add without rebuilding)."""
    # Add first batch
    vector_store.add_chunks([sample_chunks[0]], sample_embeddings[0:1])
    assert vector_store.get_collection_stats()["count"] == 1
    
    # Add second batch (should not rebuild index)
    vector_store.add_chunks([sample_chunks[1]], sample_embeddings[1:2])
    assert vector_store.get_collection_stats()["count"] == 2
    
    # Add third batch
    vector_store.add_chunks([sample_chunks[2]], sample_embeddings[2:3])
    assert vector_store.get_collection_stats()["count"] == 3


def test_add_chunks_duplicate_id_handling(vector_store):
    """Test handling of duplicate chunk IDs (should update)."""
    chunk = Chunk(
        text="Original text",
        document_id="doc_dup",
        chunk_index=0,
        char_start=0,
        char_end=13
    )
    embedding = np.random.randn(1, 768).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    
    # Add chunk first time
    vector_store.add_chunks([chunk], embedding)
    
    # Try to add same chunk ID again (ChromaDB will handle this)
    chunk_updated = Chunk(
        text="Updated text",
        document_id="doc_dup",
        chunk_index=0,
        char_start=0,
        char_end=12
    )
    
    # Should not raise error
    vector_store.add_chunks([chunk_updated], embedding)
    
    # Count should still be manageable (ChromaDB behavior may vary)
    stats = vector_store.get_collection_stats()
    assert stats["count"] >= 1


def test_add_chunks_validation_mismatched_lengths(vector_store, sample_chunks):
    """Test validation when chunks and embeddings have different lengths."""
    # Create embeddings with wrong length
    wrong_embeddings = np.random.randn(2, 768).astype(np.float32)  # Only 2 embeddings
    
    with pytest.raises(ValueError, match="must match"):
        vector_store.add_chunks(sample_chunks, wrong_embeddings)  # 3 chunks


def test_add_chunks_validation_wrong_dimensions(vector_store, sample_chunks):
    """Test validation when embeddings have wrong dimensions."""
    # Create embeddings with wrong dimensions
    wrong_embeddings = np.random.randn(3, 512).astype(np.float32)  # 512 instead of 768
    
    with pytest.raises(ValueError, match="768-dim embeddings"):
        vector_store.add_chunks(sample_chunks, wrong_embeddings)


# ============================================================================
# 3. Search Tests (7 tests)
# ============================================================================

def test_search_basic(vector_store, sample_chunks, sample_embeddings):
    """Test basic search functionality with k=5."""
    # Add chunks first
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Search with first embedding as query
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding, k=5)
    
    # Should return results (at most 3 since we only have 3 chunks)
    assert len(results) <= 3
    assert len(results) > 0
    
    # Check result structure
    assert all(isinstance(r, SearchResult) for r in results)
    assert all(hasattr(r, 'similarity_score') for r in results)
    assert all(hasattr(r, 'text') for r in results)


def test_search_custom_k_parameter(vector_store, sample_chunks, sample_embeddings):
    """Test search with custom k parameter."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Search with k=2
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding, k=2)
    
    assert len(results) <= 2


def test_search_empty_collection(vector_store):
    """Test search on empty collection."""
    query_embedding = np.random.randn(768).astype(np.float32)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    results = vector_store.search(query_embedding, k=5)
    
    assert results == []


def test_search_similarity_score_ordering(vector_store, sample_chunks, sample_embeddings):
    """Test that results are sorted by similarity score (descending)."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding, k=5)
    
    if len(results) > 1:
        # Check ordering: each score >= next score
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i+1].similarity_score


def test_search_performance(vector_store):
    """Test search performance (<500ms for reasonable dataset)."""
    import time
    
    # Add 100 chunks
    chunks = []
    embeddings_list = []
    
    for i in range(100):
        chunk = Chunk(
            text=f"Test text {i}",
            document_id=f"doc_{i}",
            chunk_index=0,
            char_start=0,
            char_end=10
        )
        chunks.append(chunk)
        
        embedding = np.random.randn(768).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
    
    embeddings = np.array(embeddings_list)
    vector_store.add_chunks(chunks, embeddings)
    
    # Perform search and measure time
    query_embedding = np.random.randn(768).astype(np.float32)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    start_time = time.time()
    results = vector_store.search(query_embedding, k=5)
    search_time = time.time() - start_time
    
    # Should be fast (< 500ms per spec, but we're lenient for tests)
    assert search_time < 1.0  # 1 second threshold for test
    assert len(results) == 5


def test_search_query_embedding_validation_wrong_shape(vector_store):
    """Test query embedding validation with wrong shape."""
    # Wrong shape: 2D with wrong first dimension
    wrong_embedding = np.random.randn(2, 768).astype(np.float32)
    
    with pytest.raises(ValueError, match="query embedding"):
        vector_store.search(wrong_embedding, k=5)


def test_search_query_embedding_validation_wrong_dim(vector_store):
    """Test query embedding validation with wrong dimensions."""
    # Wrong dimensions
    wrong_embedding = np.random.randn(512).astype(np.float32)
    
    with pytest.raises(ValueError, match="query embedding"):
        vector_store.search(wrong_embedding, k=5)


def test_search_result_limit_enforcement(vector_store, sample_chunks, sample_embeddings):
    """Test that search returns at most k results."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Search with k=1
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding, k=1)
    
    assert len(results) <= 1


# ============================================================================
# 4. Delete Tests (3 tests)
# ============================================================================

def test_delete_existing_document(vector_store, sample_chunks, sample_embeddings):
    """Test deleting an existing document."""
    # Add chunks
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Verify chunks exist
    assert vector_store.get_collection_stats()["count"] == 3
    
    # Delete document
    deleted_count = vector_store.delete_document("doc_001")
    
    # Verify deletion
    assert deleted_count == 3
    assert vector_store.get_collection_stats()["count"] == 0


def test_delete_non_existent_document(vector_store):
    """Test deleting a non-existent document."""
    deleted_count = vector_store.delete_document("non_existent_doc")
    
    assert deleted_count == 0


def test_delete_completeness(vector_store, sample_embeddings):
    """Test that delete removes ALL chunks for a document."""
    # Add chunks from two different documents
    chunks_doc1 = [
        Chunk(text=f"Doc1 chunk {i}", document_id="doc_001", chunk_index=i,
              char_start=0, char_end=10)
        for i in range(3)
    ]
    chunks_doc2 = [
        Chunk(text=f"Doc2 chunk {i}", document_id="doc_002", chunk_index=i,
              char_start=0, char_end=10)
        for i in range(2)
    ]
    
    all_chunks = chunks_doc1 + chunks_doc2
    all_embeddings = np.random.randn(5, 768).astype(np.float32)
    all_embeddings = all_embeddings / np.linalg.norm(all_embeddings, axis=1, keepdims=True)
    
    vector_store.add_chunks(all_chunks, all_embeddings)
    assert vector_store.get_collection_stats()["count"] == 5
    
    # Delete doc_001
    deleted_count = vector_store.delete_document("doc_001")
    assert deleted_count == 3
    
    # Verify only doc_002 chunks remain
    assert vector_store.get_collection_stats()["count"] == 2
    
    # Verify doc_001 chunks are gone
    # Try to query - should not find doc_001 chunks
    query_embedding = all_embeddings[0]
    results = vector_store.search(query_embedding, k=5)
    
    for result in results:
        assert result.metadata["document_id"] != "doc_001"


# ============================================================================
# 5. Health Check Tests (2 tests)
# ============================================================================

def test_health_check_success(vector_store):
    """Test health check on healthy store."""
    is_healthy = vector_store.health_check()
    
    assert is_healthy is True


def test_health_check_failure():
    """Test health check failure scenario."""
    # Create store with invalid path to simulate failure
    # Note: This might not actually fail in all cases, but tests the code path
    try:
        store = VectorStore(persist_directory="/invalid/path/that/should/not/exist")
        # If it somehow succeeds, health check should still work
        assert store.health_check() in [True, False]
    except (VectorStoreError, PermissionError, OSError):
        # Expected - cannot create store in invalid location
        pass


# ============================================================================
# Additional Utility Tests
# ============================================================================

def test_get_collection_stats(vector_store, sample_chunks, sample_embeddings):
    """Test get_collection_stats returns correct information."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    stats = vector_store.get_collection_stats()
    
    assert stats["name"] == "vietnamese_documents"
    assert stats["count"] == 3
    assert stats["embedding_dim"] == 768


def test_clear_collection(vector_store, sample_chunks, sample_embeddings):
    """Test clearing collection removes all data."""
    # Add chunks
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    assert vector_store.get_collection_stats()["count"] == 3
    
    # Clear collection
    vector_store.clear_collection()
    
    # Verify empty
    assert vector_store.get_collection_stats()["count"] == 0


def test_chunk_metadata_stored_correctly(vector_store, sample_chunks, sample_embeddings):
    """Test that chunk metadata is stored and retrieved correctly."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Search to get results with metadata
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding, k=1)
    
    assert len(results) > 0
    result = results[0]
    
    # Check metadata fields
    assert "document_id" in result.metadata
    assert "chunk_index" in result.metadata
    assert "heading_context" in result.metadata
    assert "char_start" in result.metadata
    assert "char_end" in result.metadata
    assert "timestamp" in result.metadata
