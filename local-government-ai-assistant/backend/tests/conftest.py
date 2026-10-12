"""
Pytest configuration and fixtures for RAG LLM Core System tests.

Provides shared fixtures for documents, chunks, embeddings, and test data.
"""
import pytest
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List
import tempfile
import shutil

from app.models import (
    Document, Chunk, RetrievedChunk, ChunkReference,
    IngestionStatus, IngestionResult
)


# ============================================================================
# Test Data Paths
# ============================================================================

@pytest.fixture
def test_data_dir() -> Path:
    """Path to test data directory."""
    return Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def test_documents_dir() -> Path:
    """Path to test documents directory."""
    return Path(__file__).parent / "fixtures" / "documents"


# ============================================================================
# Temporary Directories
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    tmp_dir = tempfile.mkdtemp()
    yield Path(tmp_dir)
    shutil.rmtree(tmp_dir)


# ============================================================================
# Sample Vietnamese Text
# ============================================================================

@pytest.fixture
def sample_vietnamese_text() -> str:
    """Sample Vietnamese government document text."""
    return """
Điều 1. Phạm vi điều chỉnh

Nghị định này quy định về đăng ký hộ khẩu, quản lý cư trú của công dân Việt Nam 
trên lãnh thổ nước Cộng hòa xã hội chủ nghĩa Việt Nam.

Điều 2. Đối tượng áp dụng

1. Công dân Việt Nam cư trú tại Việt Nam.
2. Cơ quan, tổ chức, cá nhân có liên quan đến đăng ký hộ khẩu và quản lý cư trú.

Điều 3. Thẩm quyền giải quyết đăng ký thường trú

1. Công an xã, phường, thị trấn có thẩm quyền giải quyết đăng ký thường trú.
2. Thời gian giải quyết không quá 03 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ.
"""


@pytest.fixture
def sample_vietnamese_text_short() -> str:
    """Short Vietnamese text for testing."""
    return "Thủ tục đăng ký hộ khẩu tại địa phương."


@pytest.fixture
def sample_vietnamese_query() -> str:
    """Sample Vietnamese query."""
    return "Thời gian giải quyết đăng ký thường trú là bao lâu?"


# ============================================================================
# Document Fixtures
# ============================================================================

@pytest.fixture
def sample_document() -> Document:
    """Sample document instance."""
    return Document(
        id="doc_001",
        text="Mẫu văn bản hành chính về thủ tục đăng ký hộ khẩu.",
        filename="test_document.txt",
        file_size=1024,
        upload_timestamp=datetime(2024, 1, 15, 10, 30, 0),
        format="txt"
    )


@pytest.fixture
def sample_documents() -> List[Document]:
    """List of sample documents."""
    return [
        Document(
            id=f"doc_{i:03d}",
            text=f"Nội dung văn bản số {i}.",
            filename=f"document_{i}.txt",
            file_size=512 * i,
            upload_timestamp=datetime(2024, 1, i % 28 + 1, 10, 0, 0),
            format="txt"
        )
        for i in range(1, 6)
    ]


# ============================================================================
# Chunk Fixtures
# ============================================================================

@pytest.fixture
def sample_chunk() -> Chunk:
    """Sample chunk instance."""
    return Chunk(
        text="Điều 1. Phạm vi điều chỉnh của nghị định.",
        document_id="doc_001",
        chunk_index=0,
        heading_context="Chương I - Quy định chung",
        char_start=0,
        char_end=50
    )


@pytest.fixture
def sample_chunks() -> List[Chunk]:
    """List of sample chunks."""
    chunks = []
    for i in range(5):
        chunks.append(
            Chunk(
                text=f"Nội dung chunk số {i}. " * 10,  # Make it realistic length
                document_id="doc_001",
                chunk_index=i,
                heading_context=f"Điều {i+1}",
                char_start=i * 200,
                char_end=(i + 1) * 200
            )
        )
    return chunks


# ============================================================================
# Embedding Fixtures
# ============================================================================

@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Sample 768-dimensional embedding vector (normalized)."""
    vec = np.random.randn(768).astype(np.float32)
    # Normalize to unit length
    vec = vec / np.linalg.norm(vec)
    return vec


@pytest.fixture
def sample_embeddings(sample_chunks) -> List[np.ndarray]:
    """Sample embeddings for chunks."""
    embeddings = []
    for _ in sample_chunks:
        vec = np.random.randn(768).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        embeddings.append(vec)
    return embeddings


# ============================================================================
# Retrieval Fixtures
# ============================================================================

@pytest.fixture
def sample_retrieved_chunk() -> RetrievedChunk:
    """Sample retrieved chunk with metadata."""
    return RetrievedChunk(
        text="Thời gian giải quyết không quá 03 ngày làm việc.",
        similarity_score=0.85,
        metadata={
            "document_id": "doc_001",
            "chunk_index": 2,
            "heading_context": "Điều 3"
        }
    )


@pytest.fixture
def sample_retrieved_chunks() -> List[RetrievedChunk]:
    """List of sample retrieved chunks sorted by similarity."""
    return [
        RetrievedChunk(
            text=f"Nội dung liên quan số {i}.",
            similarity_score=0.9 - (i * 0.1),
            metadata={
                "document_id": f"doc_{i:03d}",
                "chunk_index": i,
                "heading_context": f"Điều {i+1}"
            }
        )
        for i in range(5)
    ]


# ============================================================================
# Generation Fixtures
# ============================================================================

@pytest.fixture
def sample_chunk_references() -> List[ChunkReference]:
    """Sample chunk references for generated answer."""
    return [
        ChunkReference(
            document_id="doc_001",
            text="Thời gian giải quyết không quá 03 ngày làm việc.",
            similarity_score=0.85,
            chunk_index=2
        ),
        ChunkReference(
            document_id="doc_002",
            text="Công an xã có thẩm quyền giải quyết đăng ký.",
            similarity_score=0.78,
            chunk_index=1
        )
    ]


# ============================================================================
# Ingestion Fixtures
# ============================================================================

@pytest.fixture
def sample_ingestion_result() -> IngestionResult:
    """Sample ingestion result."""
    return IngestionResult(
        job_id="job_001",
        status=IngestionStatus.COMPLETED,
        chunk_count=10,
        document_id="doc_001",
        processing_time=2.5
    )


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from app.core.config import Settings
    
    # Create settings with test values
    settings = Settings(
        gemini_api_key="test_api_key_12345",
        gemini_model="gemini-2.0-flash-exp",
        embedding_model_name="test-model",
        chunk_min_size=200,
        chunk_max_size=1000,
        default_k=5,
        max_k=20,
        min_k=1,
        chroma_db_path="./test_chroma_db",
        log_level="DEBUG"
    )
    return settings


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@pytest.fixture
def vietnamese_chars() -> str:
    """Vietnamese character set for hypothesis strategies."""
    return (
        "aăâbcdđeêghiklmnoôơpqrstuưvxy"
        "àáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
        "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụ"
        "ừứửữựỳýỷỹỵ "
    )
