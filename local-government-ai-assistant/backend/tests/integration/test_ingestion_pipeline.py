"""Integration tests for DocumentIngestionPipeline."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import numpy as np

from app.rag.ingestion.pipeline import (
    DocumentIngestionPipeline,
    IngestionStatus,
    IngestionError
)
from app.models.data_models import Document, Chunk


@pytest.fixture
def pipeline_components(tmp_path):
    """Create mock pipeline components."""
    loader = Mock()
    cleaner = Mock()
    chunker = Mock()
    embedder = Mock()
    vector_store = Mock()
    
    return loader, cleaner, chunker, embedder, vector_store


@pytest.fixture
def pipeline(pipeline_components):
    """Create DocumentIngestionPipeline instance."""
    loader, cleaner, chunker, embedder, vector_store = pipeline_components
    return DocumentIngestionPipeline(
        loader=loader,
        cleaner=cleaner,
        chunker=chunker,
        embedding_service=embedder,
        vector_store=vector_store
    )


@pytest.mark.asyncio
async def test_end_to_end_pdf_ingestion(pipeline, pipeline_components, tmp_path):
    """Test PDF document end-to-end ingestion."""
    # Setup
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()
    
    loader, cleaner, chunker, embedder, vector_store = pipeline_components
    
    # Mock document
    mock_doc = Mock(spec=Document)
    mock_doc.text = "Original text"
    mock_doc.id = "doc_123"
    loader.load_document.return_value = mock_doc
    
    # Mock cleaned text
    cleaner.clean.return_value = "Cleaned text"
    
    # Mock chunks
    mock_chunks = [
        Chunk(text=f"Chunk {i}", document_id="doc_123", chunk_index=i)
        for i in range(3)
    ]
    chunker.chunk_document.return_value = mock_chunks
    
    # Mock embeddings
    mock_embeddings = np.random.rand(3, 768)
    embedder.embed_chunks.return_value = mock_embeddings
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Verify
    assert result.status == IngestionStatus.COMPLETED
    assert result.chunk_count == 3
    assert result.document_id is not None
    assert result.error_message is None
    
    # Verify all stages called
    loader.load_document.assert_called_once()
    cleaner.clean.assert_called_once()
    chunker.chunk_document.assert_called_once()
    embedder.embed_chunks.assert_called_once()
    vector_store.add_chunks.assert_called_once()


@pytest.mark.asyncio
async def test_failure_at_load_stage(pipeline, pipeline_components, tmp_path):
    """Test error recovery when load stage fails."""
    # Setup
    pdf_path = tmp_path / "bad.pdf"
    pdf_path.touch()
    
    loader, _, _, _, _ = pipeline_components
    loader.load_document.side_effect = Exception("File corrupted")
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Verify
    assert result.status == IngestionStatus.FAILED
    assert result.chunk_count == 0
    assert "Stage 1 (Load) failed" in result.error_message


@pytest.mark.asyncio
async def test_failure_at_chunking_stage(pipeline, pipeline_components, tmp_path):
    """Test error recovery when chunking fails."""
    # Setup
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()
    
    loader, cleaner, chunker, _, _ = pipeline_components
    
    mock_doc = Mock(spec=Document)
    mock_doc.text = "Text"
    loader.load_document.return_value = mock_doc
    cleaner.clean.return_value = "Cleaned"
    chunker.chunk_document.side_effect = Exception("Chunking failed")
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Verify
    assert result.status == IngestionStatus.FAILED
    assert "Stage 3 (Chunk) failed" in result.error_message


@pytest.mark.asyncio
async def test_concurrent_ingestion_jobs(pipeline, pipeline_components, tmp_path):
    """Test 4 concurrent ingestion jobs."""
    # Setup
    loader, cleaner, chunker, embedder, vector_store = pipeline_components
    
    async def mock_load(*args, **kwargs):
        await asyncio.sleep(0.01)  # Simulate I/O
        mock_doc = Mock(spec=Document)
        mock_doc.text = "Text"
        mock_doc.id = "doc_test"
        return mock_doc
    
    # Make load_document async-compatible
    loader.load_document.side_effect = lambda *args, **kwargs: mock_load(*args, **kwargs)
    cleaner.clean.return_value = "Cleaned"
    chunker.chunk_document.return_value = [
        Chunk(text="Chunk", document_id="doc_test", chunk_index=0)
    ]
    embedder.embed_chunks.return_value = np.random.rand(1, 768)
    
    # Create 4 files
    files = [tmp_path / f"doc{i}.pdf" for i in range(4)]
    for f in files:
        f.touch()
    
    # Execute concurrently
    tasks = [pipeline.ingest_document(f) for f in files]
    results = await asyncio.gather(*tasks)
    
    # Verify
    assert len(results) == 4
    assert all(r.status == IngestionStatus.COMPLETED for r in results)


@pytest.mark.asyncio
async def test_status_tracking_throughout_pipeline(pipeline, pipeline_components, tmp_path):
    """Test status updates throughout pipeline execution."""
    # Setup
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()
    
    loader, cleaner, chunker, embedder, vector_store = pipeline_components
    
    mock_doc = Mock(spec=Document)
    mock_doc.text = "Text"
    mock_doc.id = "doc_test"
    loader.load_document.return_value = mock_doc
    cleaner.clean.return_value = "Cleaned"
    chunker.chunk_document.return_value = [
        Chunk(text="Chunk", document_id="doc_test", chunk_index=0)
    ]
    embedder.embed_chunks.return_value = np.random.rand(1, 768)
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Verify final status
    job = await pipeline.get_status(result.job_id)
    assert job is not None
    assert job.status == IngestionStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.chunk_count == 1


@pytest.mark.asyncio
async def test_empty_chunks_failure(pipeline, pipeline_components, tmp_path):
    """Test that empty chunks result in failure."""
    # Setup
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()
    
    loader, cleaner, chunker, _, _ = pipeline_components
    
    mock_doc = Mock(spec=Document)
    mock_doc.text = "Text"
    loader.load_document.return_value = mock_doc
    cleaner.clean.return_value = "Cleaned"
    chunker.chunk_document.return_value = []  # Empty chunks
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Verify
    assert result.status == IngestionStatus.FAILED
    assert "No chunks generated" in result.error_message


@pytest.mark.asyncio
async def test_get_result_for_completed_job(pipeline, pipeline_components, tmp_path):
    """Test retrieving results for completed job."""
    # Setup
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()
    
    loader, cleaner, chunker, embedder, vector_store = pipeline_components
    
    mock_doc = Mock(spec=Document)
    mock_doc.text = "Text"
    mock_doc.id = "doc_test"
    loader.load_document.return_value = mock_doc
    cleaner.clean.return_value = "Cleaned"
    chunker.chunk_document.return_value = [
        Chunk(text="Chunk", document_id="doc_test", chunk_index=0)
    ]
    embedder.embed_chunks.return_value = np.random.rand(1, 768)
    
    # Execute
    result = await pipeline.ingest_document(pdf_path)
    
    # Get result
    retrieved_result = await pipeline.get_result(result.job_id)
    
    # Verify
    assert retrieved_result is not None
    assert retrieved_result.job_id == result.job_id
    assert retrieved_result.status == IngestionStatus.COMPLETED
    assert retrieved_result.chunk_count == 1


@pytest.mark.asyncio
async def test_get_result_for_nonexistent_job(pipeline):
    """Test retrieving results for non-existent job returns None."""
    result = await pipeline.get_result("nonexistent_job_id")
    assert result is None
