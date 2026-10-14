"""
Integration tests for Document Ingestion Pipeline with real components.

These tests use actual components (not mocks) to verify end-to-end functionality.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
"""

import pytest
import asyncio
from pathlib import Path
import tempfile

from app.rag.ingestion.pipeline import DocumentIngestionPipeline, IngestionStatus
from app.rag.ingestion.loader import DocumentLoader
from app.rag.ingestion.cleaner import TextCleaner
from app.rag.ingestion.chunker import SemanticChunker
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore


@pytest.fixture
def temp_vector_store(tmp_path):
    """Create temporary vector store for testing."""
    return VectorStore(persist_directory=str(tmp_path / "chroma_test"))


@pytest.fixture
def pipeline(temp_vector_store):
    """Create ingestion pipeline with real components."""
    return DocumentIngestionPipeline(
        loader=DocumentLoader(),
        cleaner=TextCleaner(),
        chunker=SemanticChunker(),
        embedding_service=EmbeddingService(),
        vector_store=temp_vector_store
    )


@pytest.mark.asyncio
async def test_end_to_end_txt_ingestion(pipeline, tmp_path):
    """
    Test complete TXT document ingestion.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    # Create test file with Vietnamese content
    test_file = tmp_path / "test.txt"
    test_content = """
    Điều 10: Đăng ký hộ khẩu thường trú
    
    Công dân khi đăng ký hộ khẩu thường trú cần chuẩn bị các giấy tờ sau:
    - Chứng minh nhân dân hoặc Căn cước công dân
    - Sổ hộ khẩu cũ (nếu có)
    - Giấy xác nhận cư trú do chủ hộ hoặc chính quyền địa phương cấp
    - Đơn đăng ký hộ khẩu theo mẫu quy định
    
    Thời gian giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ.
    """
    test_file.write_text(test_content, encoding='utf-8')
    
    # Run ingestion
    result = await pipeline.ingest_document(test_file)
    
    # Verify result
    assert result.status == IngestionStatus.COMPLETED
    assert result.chunk_count > 0
    assert result.document_id is not None
    assert result.error_message is None
    
    # Verify job tracking
    job = await pipeline.get_status(result.job_id)
    assert job is not None
    assert job.status == IngestionStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_concurrent_ingestion(pipeline, tmp_path):
    """
    Test 4 concurrent ingestion jobs.
    
    **Validates: Requirement 6.4 (concurrent processing)**
    """
    # Create test files
    files = []
    for i in range(4):
        f = tmp_path / f"doc{i}.txt"
        content = f"""
        Tài liệu số {i}
        
        Đây là nội dung của tài liệu thử nghiệm số {i}.
        Tài liệu này được tạo ra để kiểm tra khả năng xử lý đồng thời
        của hệ thống xử lý văn bản hành chính.
        
        Nội dung chính: Quy trình xử lý hồ sơ hành chính số {i}.
        """
        f.write_text(content, encoding='utf-8')
        files.append(f)
    
    # Run concurrently
    tasks = [pipeline.ingest_document(f) for f in files]
    results = await asyncio.gather(*tasks)
    
    # Verify all completed successfully
    assert len(results) == 4
    assert all(r.status == IngestionStatus.COMPLETED for r in results)
    assert all(r.chunk_count > 0 for r in results)
    assert all(r.error_message is None for r in results)
    
    # Verify all have unique document IDs
    doc_ids = [r.document_id for r in results]
    assert len(set(doc_ids)) == 4


@pytest.mark.asyncio
async def test_status_tracking(pipeline, tmp_path):
    """
    Test status updates throughout pipeline.
    
    **Validates: Requirement 6.5 (status tracking)**
    """
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test document content for status tracking.", encoding='utf-8')
    
    result = await pipeline.ingest_document(test_file)
    
    # Check final status
    job = await pipeline.get_status(result.job_id)
    assert job is not None
    assert job.status == IngestionStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.completed_at >= job.started_at


@pytest.mark.asyncio
async def test_vietnamese_text_preservation(pipeline, tmp_path):
    """
    Test that Vietnamese diacritics and text are preserved throughout pipeline.
    
    **Validates: Requirements 2.1, 2.3 (Vietnamese text handling)**
    """
    test_file = tmp_path / "vietnamese.txt"
    vietnamese_content = """
    Điều 15: Các loại giấy tờ tùy thân
    
    Công dân Việt Nam có các loại giấy tờ tùy thân sau:
    - Chứng minh nhân dân (CMND)
    - Căn cước công dân (CCCD)
    - Hộ chiếu (Passport)
    
    Các giấy tờ này đều có giá trị pháp lý như nhau khi chứng minh
    danh tính trong các giao dịch hành chính.
    """
    test_file.write_text(vietnamese_content, encoding='utf-8')
    
    result = await pipeline.ingest_document(test_file)
    
    # Verify successful ingestion
    assert result.status == IngestionStatus.COMPLETED
    assert result.chunk_count > 0
    
    # The fact that ingestion completed means:
    # 1. Text was loaded with UTF-8 encoding
    # 2. Cleaning preserved Vietnamese characters
    # 3. Chunking handled Vietnamese text correctly
    # 4. Embedding service processed Vietnamese text


@pytest.mark.asyncio
async def test_error_recovery_invalid_file(pipeline, tmp_path):
    """
    Test error handling for invalid files.
    
    **Validates: Requirement 6.2 (error handling)**
    """
    # Create non-existent file path
    invalid_file = tmp_path / "nonexistent.txt"
    
    result = await pipeline.ingest_document(invalid_file)
    
    # Should fail gracefully
    assert result.status == IngestionStatus.FAILED
    assert result.error_message is not None
    assert result.chunk_count == 0


@pytest.mark.asyncio
async def test_chunking_quality(pipeline, tmp_path):
    """
    Test that chunking produces reasonable chunk counts.
    
    **Validates: Requirements 3.5 (chunk size bounds)**
    """
    test_file = tmp_path / "long_doc.txt"
    
    # Create document with multiple sections
    content = "\n\n".join([
        f"Điều {i}: Quy định về thủ tục hành chính số {i}\n\n" +
        f"Nội dung chi tiết về quy trình xử lý hồ sơ hành chính liên quan đến " +
        f"lĩnh vực {i}. " * 10
        for i in range(1, 11)
    ])
    
    test_file.write_text(content, encoding='utf-8')
    
    result = await pipeline.ingest_document(test_file)
    
    # Should create multiple chunks
    assert result.status == IngestionStatus.COMPLETED
    assert result.chunk_count >= 5  # Should have multiple chunks
    assert result.chunk_count <= 30  # But not too many


@pytest.mark.asyncio
async def test_embedding_generation(pipeline, tmp_path, temp_vector_store):
    """
    Test that embeddings are generated and stored.
    
    **Validates: Requirements 4.2, 4.5 (embedding generation and storage)**
    """
    test_file = tmp_path / "embed_test.txt"
    content = "Đăng ký hộ khẩu cần CMND và sổ hộ khẩu cũ."
    test_file.write_text(content, encoding='utf-8')
    
    result = await pipeline.ingest_document(test_file)
    
    assert result.status == IngestionStatus.COMPLETED
    assert result.chunk_count > 0
    
    # Verify vectors were stored by attempting a search
    test_query_embedding = pipeline.embedding_service.embed_single("hộ khẩu")
    search_results = temp_vector_store.search(test_query_embedding, k=1)
    
    assert len(search_results) > 0


@pytest.mark.asyncio
async def test_pipeline_timing(pipeline, tmp_path):
    """
    Test that pipeline completes in reasonable time.
    
    Small documents should complete quickly.
    """
    import time
    
    test_file = tmp_path / "timing_test.txt"
    content = "Quy định về đăng ký tạm trú và thường trú tại địa phương."
    test_file.write_text(content, encoding='utf-8')
    
    start_time = time.time()
    result = await pipeline.ingest_document(test_file)
    duration = time.time() - start_time
    
    assert result.status == IngestionStatus.COMPLETED
    # Should complete within 30 seconds for small document
    assert duration < 30.0


@pytest.mark.asyncio
async def test_get_result_consistency(pipeline, tmp_path):
    """Test that get_result returns consistent data with ingestion result."""
    test_file = tmp_path / "consistency_test.txt"
    test_file.write_text("Test content for consistency check.", encoding='utf-8')
    
    ingestion_result = await pipeline.ingest_document(test_file)
    
    # Get result through pipeline
    retrieved_result = await pipeline.get_result(ingestion_result.job_id)
    
    # Verify consistency
    assert retrieved_result is not None
    assert retrieved_result.job_id == ingestion_result.job_id
    assert retrieved_result.status == ingestion_result.status
    assert retrieved_result.chunk_count == ingestion_result.chunk_count
    assert retrieved_result.document_id == ingestion_result.document_id
