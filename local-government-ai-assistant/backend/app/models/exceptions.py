"""
Exception hierarchy for RAG LLM Core System.

Defines custom exceptions for different failure modes across the system.
Implements requirement 16.5 for descriptive error messages.
"""


class RAGException(Exception):
    """Base exception for all RAG system errors."""
    pass


class DocumentLoadError(RAGException):
    """Failed to load or extract text from document."""
    pass


class UnsupportedFormatError(DocumentLoadError):
    """Document format is not supported."""
    pass


class ExtractionError(DocumentLoadError):
    """Failed to extract text content from document."""
    pass


class EmbeddingError(RAGException):
    """Failed to generate embeddings."""
    pass


class VectorStoreError(RAGException):
    """Vector store operation failed."""
    pass


class RAGValidationError(RAGException):
    """Input validation failed."""
    pass


class ValidationError(RAGValidationError):
    """Generic validation error with descriptive message."""
    pass


class RAGPipelineError(RAGException):
    """Pipeline execution failed at a specific stage."""
    
    def __init__(self, message: str, stage: str = None):
        """
        Initialize pipeline error with stage information.
        
        Args:
            message: Error description
            stage: Pipeline stage where error occurred
        """
        super().__init__(message)
        self.stage = stage


class LLMGenerationError(RAGException):
    """LLM answer generation failed."""
    pass


class ConfigurationError(RAGException):
    """System configuration is invalid or incomplete."""
    pass
