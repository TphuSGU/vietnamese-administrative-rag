"""
Dependency injection for RAG pipeline components.

Creates singleton instances of heavy services (models, vector stores)
to avoid repeated initialization overhead.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.database.session import get_db
from app.models.db_models import User
from app.core.security import decode_access_token
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline
from app.rag.ingestion.loader import DocumentLoader
from app.rag.ingestion.cleaner import TextCleaner
from app.rag.ingestion.chunker import SemanticChunker
from app.rag.ingestion.pipeline import DocumentIngestionPipeline
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
        min_evidence_ratio=0.25,
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
        min_similarity=settings.retrieval_min_similarity,
        use_reranking=settings.retrieval_use_reranking,
        bm25s_persist_dir=settings.bm25s_persist_dir
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


@lru_cache()
def get_ingestion_pipeline() -> DocumentIngestionPipeline:
    """
    Get singleton DocumentIngestionPipeline instance.

    Shares the embedding service and vector store singletons so uploads
    do not reload the embedding model on every request.

    Returns:
        DocumentIngestionPipeline ready for document ingestion
    """
    logger.info("Creating DocumentIngestionPipeline")

    return DocumentIngestionPipeline(
        loader=DocumentLoader(),
        cleaner=TextCleaner(),
        chunker=SemanticChunker(
            min_size=settings.chunk_min_size,
            max_size=settings.chunk_max_size
        ),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store()
    )



# ============================================================================
# Authentication dependencies
# ============================================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the current user when a valid Bearer token is supplied."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        user_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        return None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid Bearer token and return the active user."""
    if not token:
        raise _credentials_error()
    payload = decode_access_token(token)
    if not payload:
        raise _credentials_error()
    try:
        user_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise _credentials_error()

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cần quyền quản trị viên",
        )
    return user
