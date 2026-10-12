"""
Unit tests for core data models.

Tests model creation, validation, and data completeness.
"""
import pytest
from datetime import datetime

from app.models import (
    Document, Chunk, IngestionStatus, IngestionResult,
    RetrievedChunk, ChunkReference, GeneratedAnswer, RAGResponse
)


class TestDocumentModel:
    """Tests for Document dataclass."""
    
    def test_create_document(self, sample_document):
        """Test creating a valid document."""
        assert sample_document.id == "doc_001"
        assert sample_document.filename == "test_document.txt"
        assert sample_document.file_size == 1024
        assert isinstance(sample_document.upload_timestamp, datetime)
    
    def test_document_requires_id(self):
        """Test that document ID is required."""
        with pytest.raises(ValueError, match="Document ID is required"):
            Document(
                id="",
                text="test",
                filename="test.txt",
                file_size=100,
                upload_timestamp=datetime.now(),
                format="txt"
            )
    
    def test_document_requires_filename(self):
        """Test that document filename is required."""
        with pytest.raises(ValueError, match="filename is required"):
            Document(
                id="doc_001",
                text="test",
                filename="",
                file_size=100,
                upload_timestamp=datetime.now(),
                format="txt"
            )


class TestChunkModel:
    """Tests for Chunk dataclass."""
    
    def test_create_chunk(self, sample_chunk):
        """Test creating a valid chunk."""
        assert sample_chunk.text is not None
        assert sample_chunk.document_id == "doc_001"
        assert sample_chunk.chunk_index == 0
        assert sample_chunk.heading_context is not None
    
    def test_chunk_requires_text(self):
        """Test that chunk text cannot be empty."""
        with pytest.raises(ValueError, match="text cannot be empty"):
            Chunk(
                text="",
                document_id="doc_001",
                chunk_index=0
            )
    
    def test_chunk_requires_document_id(self):
        """Test that chunk document_id is required."""
        with pytest.raises(ValueError, match="document_id is required"):
            Chunk(
                text="test",
                document_id="",
                chunk_index=0
            )
    
    def test_chunk_index_must_be_non_negative(self):
        """Test that chunk index must be non-negative."""
        with pytest.raises(ValueError, match="index must be non-negative"):
            Chunk(
                text="test",
                document_id="doc_001",
                chunk_index=-1
            )
    
    def test_chunk_length_property(self, sample_chunk):
        """Test chunk length property."""
        assert sample_chunk.length == len(sample_chunk.text)
    
    def test_chunk_to_dict(self, sample_chunk):
        """Test chunk conversion to dictionary."""
        chunk_dict = sample_chunk.to_dict()
        assert chunk_dict["text"] == sample_chunk.text
        assert chunk_dict["document_id"] == sample_chunk.document_id
        assert chunk_dict["chunk_index"] == sample_chunk.chunk_index


class TestIngestionStatus:
    """Tests for IngestionStatus enum."""
    
    def test_ingestion_status_values(self):
        """Test all ingestion status values."""
        assert IngestionStatus.PENDING.value == "pending"
        assert IngestionStatus.PROCESSING.value == "processing"
        assert IngestionStatus.COMPLETED.value == "completed"
        assert IngestionStatus.FAILED.value == "failed"


class TestIngestionResult:
    """Tests for IngestionResult dataclass."""
    
    def test_create_ingestion_result(self, sample_ingestion_result):
        """Test creating a valid ingestion result."""
        assert sample_ingestion_result.job_id == "job_001"
        assert sample_ingestion_result.status == IngestionStatus.COMPLETED
        assert sample_ingestion_result.chunk_count == 10
        assert sample_ingestion_result.document_id == "doc_001"
    
    def test_ingestion_result_is_successful(self, sample_ingestion_result):
        """Test is_successful method."""
        assert sample_ingestion_result.is_successful() is True
        
        failed_result = IngestionResult(
            job_id="job_002",
            status=IngestionStatus.FAILED,
            chunk_count=0,
            document_id="doc_002",
            error_message="Test error"
        )
        assert failed_result.is_successful() is False


class TestRetrievedChunk:
    """Tests for RetrievedChunk dataclass."""
    
    def test_create_retrieved_chunk(self, sample_retrieved_chunk):
        """Test creating a valid retrieved chunk."""
        assert sample_retrieved_chunk.text is not None
        assert sample_retrieved_chunk.similarity_score == 0.85
        assert isinstance(sample_retrieved_chunk.metadata, dict)
    
    def test_retrieved_chunk_requires_similarity_score(self):
        """Test that similarity score is required."""
        with pytest.raises(ValueError, match="Similarity score is required"):
            RetrievedChunk(
                text="test",
                similarity_score=None,
                metadata={}
            )
    
    def test_retrieved_chunk_document_id_property(self, sample_retrieved_chunk):
        """Test document_id property extraction."""
        assert sample_retrieved_chunk.document_id == "doc_001"
    
    def test_retrieved_chunk_heading_context_property(self, sample_retrieved_chunk):
        """Test heading_context property extraction."""
        assert sample_retrieved_chunk.heading_context == "Điều 3"


class TestGeneratedAnswer:
    """Tests for GeneratedAnswer dataclass."""
    
    def test_create_generated_answer(self, sample_chunk_references):
        """Test creating a valid generated answer."""
        answer = GeneratedAnswer(
            answer="Thời gian giải quyết là 03 ngày làm việc.",
            source_chunks=sample_chunk_references,
            model="gemini-2.0-flash-exp",
            tokens_used=50
        )
        assert answer.answer is not None
        assert len(answer.source_chunks) == 2
        assert answer.model == "gemini-2.0-flash-exp"
    
    def test_generated_answer_requires_answer_text(self, sample_chunk_references):
        """Test that answer text is required."""
        with pytest.raises(ValueError, match="Answer text is required"):
            GeneratedAnswer(
                answer="",
                source_chunks=sample_chunk_references,
                model="test",
                tokens_used=10
            )


class TestRAGResponse:
    """Tests for RAGResponse dataclass."""
    
    def test_create_rag_response(self, sample_chunk_references):
        """Test creating a valid RAG response."""
        response = RAGResponse(
            query_id="q_001",
            answer="Test answer",
            source_chunks=sample_chunk_references,
            relevance_scores=[0.85, 0.78],
            processing_time=1.5,
            model="gemini-2.0-flash-exp"
        )
        assert response.query_id == "q_001"
        assert response.answer == "Test answer"
        assert len(response.source_chunks) == 2
        assert len(response.relevance_scores) == 2
    
    def test_rag_response_to_dict(self, sample_chunk_references):
        """Test RAG response conversion to dictionary."""
        response = RAGResponse(
            query_id="q_001",
            answer="Test answer",
            source_chunks=sample_chunk_references,
            relevance_scores=[0.85, 0.78],
            processing_time=1.5,
            model="gemini-2.0-flash-exp"
        )
        response_dict = response.to_dict()
        assert response_dict["query_id"] == "q_001"
        assert response_dict["answer"] == "Test answer"
        assert "source_chunks" in response_dict
        assert "relevance_scores" in response_dict
