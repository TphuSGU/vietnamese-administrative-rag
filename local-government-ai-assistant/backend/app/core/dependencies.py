"""
Dependency injection for RAG pipeline components.

Creates singleton instances of heavy services (models, vector stores)
to avoid repeated initialization overhead.
"""

from functools import lru_cache
from pathlib import Path

from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_embedding_service() -> EmbeddingService:
    """
    Get singleton EmbeddingService instance.
    
    Returns:
        EmbeddingService configured with vietnamese-bi-encoder
    """
    logger.info("Initializing EmbeddingService")
    
    model_path = settings.embedding_model_path if settings.embedding_model_path else None
    model_name = model_path if model_path else settings.embedding_model_name
    
    return EmbeddingService(
        model_name=model_name,
        batch_size=settings.embedding_batch_size
    )


@lru_cache()
def get_vector_store() -> VectorStore:
    """
    Get singleton VectorStore instance.
    
    Returns:
        VectorStore configured with ChromaDB
    """
    logger.info("Initializing VectorStore")
    
    return VectorStore(
        persist_directory=settings.chroma_db_path
    )


@lru_cache()
def get_llm_service() -> LLMService:
    """
    Get singleton LLMService instance.
    
    Returns:
        LLMService configured with Gemini API
    """
    logger.info("Initializing LLMService")
    
    return LLMService(
        api_key=settings.gemini_api_key
    )


def get_output_validator() -> OutputValidator:
    """
    Get OutputValidator instance.
    
    Returns:
        OutputValidator with default configuration
    """
    return OutputValidator(
        min_evidence_ratio=0.4,
        strict_mode=False
    )


def get_hybrid_retriever() -> HybridRetriever:
    """
    Get HybridRetriever with all dependencies.
        
    Returns:
        HybridRetriever configured for hybrid search
    """
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()
    
    logger.info("Creating HybridRetriever")
    
    return HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,  # 60% weight on semantic, 40% on keyword
        min_similarity=0.7,
        use_reranking=True
    )


def get_hybrid_pipeline() -> HybridRAGPipeline:
    """
    Get complete HybridRAGPipeline with all components.
        
    Returns:
        HybridRAGPipeline ready for queries
    """
    hybrid_retriever = get_hybrid_retriever()
    llm_service = get_llm_service()
    output_validator = get_output_validator()
    
    logger.info("Creating HybridRAGPipeline")
    
    log_dir = Path("./logs")
    
    return HybridRAGPipeline(
        hybrid_retriever=hybrid_retriever,
        llm_service=llm_service,
        output_validator=output_validator,
        log_dir=log_dir
    )
