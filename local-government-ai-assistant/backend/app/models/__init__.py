"""
Data models and exceptions for RAG LLM Core System.
"""
from .data_models import (
    Document,
    Chunk,
    IngestionStatus,
    IngestionResult,
    SearchResult,
    RetrievedChunk,
    ChunkReference,
    GeneratedAnswer,
    RAGResponse,
    EvaluationDataset,
    EvaluationReport,
)
from .exceptions import (
    RAGException,
    DocumentLoadError,
    UnsupportedFormatError,
    ExtractionError,
    EmbeddingError,
    VectorStoreError,
    RAGValidationError,
    ValidationError,
    RAGPipelineError,
    LLMGenerationError,
    ConfigurationError,
)

__all__ = [
    # Data Models
    "Document",
    "Chunk",
    "IngestionStatus",
    "IngestionResult",
    "SearchResult",
    "RetrievedChunk",
    "ChunkReference",
    "GeneratedAnswer",
    "RAGResponse",
    "EvaluationDataset",
    "EvaluationReport",
    # Exceptions
    "RAGException",
    "DocumentLoadError",
    "UnsupportedFormatError",
    "ExtractionError",
    "EmbeddingError",
    "VectorStoreError",
    "RAGValidationError",
    "ValidationError",
    "RAGPipelineError",
    "LLMGenerationError",
    "ConfigurationError",
]
