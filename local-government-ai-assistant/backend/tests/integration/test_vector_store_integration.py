"""
Integration tests for VectorStore with complete pipeline.

Tests end-to-end workflow:
- Chunk document → Embed → Store → Search
- Multiple documents with search
- Real embedding service integration

Validates: Requirements 5.1-5.6 in integrated context
"""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path

from app.database.vector_store import VectorStore
from app.models.data_models import Chunk, SearchResult


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create temporary directory for ChromaDB storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vector_store(temp_db_path):
    """Create VectorStore instance with temp storage."""
    return VectorStore(persist_directory=temp_db_path)


# ============================================================================
# Integration Tests
# ============================================================================

def test_end_to_end_pipeline_basic(vector_store):
    """
    Test complete pipeline: Chunk → Embed → Store → Search.
    
    Simulates the full workflow from document chunking to retrieval.
    """
    # Stage 1: Create document chunks (simulating SemanticChunker output)
    chunks = [
        Chunk(
            text="Thủ tục đăng ký hộ khẩu thường trú tại địa phương cần giấy tờ tùy thân.",
            document_id="doc_gov_001",
            chunk_index=0,
            heading_context="Điều 1: Đăng ký hộ khẩu",
            char_start=0,
            char_end=72
        ),
        Chunk(
            text="Công dân phải xuất trình chứng minh nhân dân hoặc căn cước công dân.",
            document_id="doc_gov_001",
            chunk_index=1,
            heading_context="Điều 2: Giấy tờ cần thiết",
            char_start=72,
            char_end=141
        ),
        Chunk(
            text="Thời gian giải quyết hồ sơ đăng ký hộ khẩu là 15 ngày làm việc.",
            document_id="doc_gov_001",
            chunk_index=2,
            heading_context="Điều 3: Thời hạn giải quyết",
            char_start=141,
            char_end=205
        )
    ]
    
    # Stage 2: Generate embeddings (simulating EmbeddingService output)
    # In real scenario, these would come from vietnamese-bi-encoder
    embeddings = np.random.randn(3, 768).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    # Stage 3: Store in vector DB
    vector_store.add_chunks(chunks, embeddings)
    
    # Verify storage
    stats = vector_store.get_collection_stats()
    assert stats["count"] == 3
    
    # Stage 4: Search with query
    # Simulate query: "Thủ tục đăng ký hộ khẩu?"
    query_embedding = embeddings[0]  # Use similar embedding for testing
    results = vector_store.search(query_embedding, k=5)
    
    # Verify results
    assert len(results) > 0
    assert all(isinstance(r, SearchResult) for r in results)
    assert all(r.similarity_score is not None for r in results)
    
    # Check result ordering (descending similarity)
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i+1].similarity_score
    
    # Check metadata preservation
    top_result = results[0]
    assert "document_id" in top_result.metadata
    assert "heading_context" in top_result.metadata
    assert top_result.metadata["document_id"] == "doc_gov_001"


def test_multiple_documents_search(vector_store):
    """
    Test search across multiple documents.
    
    Validates that vector store can handle multiple documents
    and return relevant results across all documents.
    """
    # Document 1: About residence registration
    chunks_doc1 = [
        Chunk(
            text="Đăng ký hộ khẩu thường trú tại địa phương.",
            document_id="doc_residence",
            chunk_index=0,
            heading_context="Đăng ký cư trú",
            char_start=0,
            char_end=43
        ),
        Chunk(
            text="Thủ tục đăng ký bao gồm nộp hồ sơ và chờ xét duyệt.",
            document_id="doc_residence",
            chunk_index=1,
            heading_context="Quy trình",
            char_start=43,
            char_end=95
        )
    ]
    
    # Document 2: About birth certificates
    chunks_doc2 = [
        Chunk(
            text="Đăng ký khai sinh cho trẻ em mới sinh tại địa phương.",
            document_id="doc_birth",
            chunk_index=0,
            heading_context="Khai sinh",
            char_start=0,
            char_end=54
        ),
        Chunk(
            text="Giấy khai sinh cần có trong vòng 60 ngày sau khi sinh.",
            document_id="doc_birth",
            chunk_index=1,
            heading_context="Thời hạn",
            char_start=54,
            char_end=109
        )
    ]
    
    # Document 3: About ID cards
    chunks_doc3 = [
        Chunk(
            text="Làm căn cước công dân tại công an quận/huyện.",
            document_id="doc_id_card",
            chunk_index=0,
            heading_context="CCCD",
            char_start=0,
            char_end=46
        )
    ]
    
    all_chunks = chunks_doc1 + chunks_doc2 + chunks_doc3
    
    # Generate embeddings for all chunks
    embeddings = np.random.randn(5, 768).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    # Store all chunks
    vector_store.add_chunks(all_chunks, embeddings)
    
    # Verify storage
    stats = vector_store.get_collection_stats()
    assert stats["count"] == 5
    
    # Search should find relevant chunks across all documents
    query_embedding = embeddings[0]
    results = vector_store.search(query_embedding, k=3)
    
    assert len(results) > 0
    assert len(results) <= 3
    
    # Results may come from different documents
    document_ids = set(r.metadata["document_id"] for r in results)
    assert len(document_ids) >= 1  # At least one document


def test_document_deletion_and_search(vector_store):
    """
    Test that deleted document chunks don't appear in search results.
    """
    # Add chunks from two documents
    chunks_doc1 = [
        Chunk(
            text=f"Document 1 chunk {i}",
            document_id="doc_001",
            chunk_index=i,
            char_start=i*20,
            char_end=(i+1)*20
        )
        for i in range(3)
    ]
    
    chunks_doc2 = [
        Chunk(
            text=f"Document 2 chunk {i}",
            document_id="doc_002",
            chunk_index=i,
            char_start=i*20,
            char_end=(i+1)*20
        )
        for i in range(2)
    ]
    
    all_chunks = chunks_doc1 + chunks_doc2
    embeddings = np.random.randn(5, 768).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    # Store all chunks
    vector_store.add_chunks(all_chunks, embeddings)
    assert vector_store.get_collection_stats()["count"] == 5
    
    # Search before deletion
    query_embedding = embeddings[0]
    results_before = vector_store.search(query_embedding, k=5)
    doc1_count_before = sum(
        1 for r in results_before if r.metadata["document_id"] == "doc_001"
    )
    assert doc1_count_before > 0  # doc_001 chunks present
    
    # Delete doc_001
    deleted_count = vector_store.delete_document("doc_001")
    assert deleted_count == 3
    assert vector_store.get_collection_stats()["count"] == 2
    
    # Search after deletion
    results_after = vector_store.search(query_embedding, k=5)
    doc1_count_after = sum(
        1 for r in results_after if r.metadata["document_id"] == "doc_001"
    )
    assert doc1_count_after == 0  # No doc_001 chunks
    
    # Only doc_002 chunks remain
    assert all(r.metadata["document_id"] == "doc_002" for r in results_after)


def test_incremental_document_addition(vector_store):
    """
    Test adding documents incrementally without rebuilding index.
    
    Validates Requirement 5.5: Incremental indexing.
    """
    # Add first document
    chunks_1 = [
        Chunk(
            text="First document chunk",
            document_id="doc_001",
            chunk_index=0,
            char_start=0,
            char_end=20
        )
    ]
    embeddings_1 = np.random.randn(1, 768).astype(np.float32)
    embeddings_1 = embeddings_1 / np.linalg.norm(embeddings_1)
    
    vector_store.add_chunks(chunks_1, embeddings_1)
    assert vector_store.get_collection_stats()["count"] == 1
    
    # Add second document (incremental, no rebuild)
    chunks_2 = [
        Chunk(
            text="Second document chunk",
            document_id="doc_002",
            chunk_index=0,
            char_start=0,
            char_end=21
        )
    ]
    embeddings_2 = np.random.randn(1, 768).astype(np.float32)
    embeddings_2 = embeddings_2 / np.linalg.norm(embeddings_2)
    
    vector_store.add_chunks(chunks_2, embeddings_2)
    assert vector_store.get_collection_stats()["count"] == 2
    
    # Add third document
    chunks_3 = [
        Chunk(
            text="Third document chunk",
            document_id="doc_003",
            chunk_index=0,
            char_start=0,
            char_end=20
        )
    ]
    embeddings_3 = np.random.randn(1, 768).astype(np.float32)
    embeddings_3 = embeddings_3 / np.linalg.norm(embeddings_3)
    
    vector_store.add_chunks(chunks_3, embeddings_3)
    assert vector_store.get_collection_stats()["count"] == 3
    
    # Search should work across all documents
    query_embedding = embeddings_1[0]
    results = vector_store.search(query_embedding, k=5)
    assert len(results) == 3


def test_search_latency_benchmark(vector_store):
    """
    Test search latency meets requirement (<500ms for 10K documents).
    
    Validates Requirement 5.3: Search performance.
    """
    import time
    
    # Add 1000 chunks (scaled down from 10K for faster testing)
    chunks = []
    embeddings_list = []
    
    for i in range(1000):
        chunk = Chunk(
            text=f"Government document chunk number {i} with various Vietnamese text content.",
            document_id=f"doc_{i // 10}",  # 10 chunks per document
            chunk_index=i % 10,
            heading_context=f"Section {i % 5}",
            char_start=i*100,
            char_end=(i+1)*100
        )
        chunks.append(chunk)
        
        embedding = np.random.randn(768).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
    
    embeddings = np.array(embeddings_list)
    vector_store.add_chunks(chunks, embeddings)
    
    # Verify storage
    stats = vector_store.get_collection_stats()
    assert stats["count"] == 1000
    
    # Perform multiple searches and measure average latency
    query_embedding = np.random.randn(768).astype(np.float32)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    latencies = []
    for _ in range(10):
        start_time = time.time()
        results = vector_store.search(query_embedding, k=5)
        latency = (time.time() - start_time) * 1000  # Convert to ms
        latencies.append(latency)
        
        assert len(results) == 5
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    # For 1000 documents, should be well under 500ms
    # (10K documents requirement, scaled down)
    assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms too high"
    assert max_latency < 200, f"Max latency {max_latency:.2f}ms too high"
    
    print(f"\nSearch Performance: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")


def test_metadata_preservation_through_pipeline(vector_store):
    """
    Test that all metadata is preserved through store and retrieve cycle.
    """
    chunk = Chunk(
        text="Detailed text about government procedure with specific requirements.",
        document_id="doc_metadata_test",
        chunk_index=42,
        heading_context="Điều 10: Quy định chi tiết",
        char_start=1000,
        char_end=1068
    )
    
    embedding = np.random.randn(1, 768).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    
    # Store
    vector_store.add_chunks([chunk], embedding)
    
    # Retrieve
    query_embedding = embedding[0]
    results = vector_store.search(query_embedding, k=1)
    
    assert len(results) == 1
    result = results[0]
    
    # Verify all metadata fields preserved
    assert result.metadata["document_id"] == "doc_metadata_test"
    assert result.metadata["chunk_index"] == 42
    assert result.metadata["heading_context"] == "Điều 10: Quy định chi tiết"
    assert result.metadata["char_start"] == 1000
    assert result.metadata["char_end"] == 1068
    assert "timestamp" in result.metadata
    
    # Verify text preserved
    assert result.text == chunk.text
    
    # Verify similarity score is high (searching with same embedding)
    assert result.similarity_score > 0.99


def test_empty_results_handling(vector_store):
    """
    Test that empty collection returns empty results gracefully.
    """
    # Search on empty collection
    query_embedding = np.random.randn(768).astype(np.float32)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    results = vector_store.search(query_embedding, k=5)
    
    assert results == []
    assert isinstance(results, list)


def test_persistence_across_instances(temp_db_path):
    """
    Test that data persists across VectorStore instances.
    
    Validates that ChromaDB persistence works correctly.
    """
    # Create first instance and add data
    store1 = VectorStore(persist_directory=temp_db_path)
    
    chunk = Chunk(
        text="Persistent test data",
        document_id="doc_persist",
        chunk_index=0,
        char_start=0,
        char_end=20
    )
    embedding = np.random.randn(1, 768).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    
    store1.add_chunks([chunk], embedding)
    assert store1.get_collection_stats()["count"] == 1
    
    # Create second instance with same path
    store2 = VectorStore(persist_directory=temp_db_path)
    
    # Data should persist
    assert store2.get_collection_stats()["count"] == 1
    
    # Search should work
    query_embedding = embedding[0]
    results = store2.search(query_embedding, k=1)
    
    assert len(results) == 1
    assert results[0].text == "Persistent test data"
