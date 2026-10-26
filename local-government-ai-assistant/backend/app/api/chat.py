"""
Chat API endpoints for RAG query functionality.

Provides:
- POST /api/v1/chat/query - Main RAG query endpoint
- GET /api/v1/chat/health - Health check for RAG components
- GET /api/v1/chat/stats - Pipeline statistics
"""

import time
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline
from app.models.data_models import RAGResponse
from app.models.db_models import User
from app.models.exceptions import RAGValidationError, RAGException
from app.core.dependencies import (
    get_hybrid_pipeline,
    get_embedding_service,
    get_vector_store,
    get_llm_service,
    get_output_validator,
    get_optional_user,
)
from app.database.session import get_db
from app.repositories import conversations as conversation_repo
from app.services.conversations import sources_payload
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for RAG query."""
    
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Câu hỏi của người dùng (tiếng Việt)"
    )
    k: int = Field(
        5,
        ge=1,
        le=20,
        description="Số lượng tài liệu tham khảo"
    )
    conversation_id: Optional[UUID] = Field(
        None,
        description="ID cuộc hội thoại (cần đăng nhập) để lưu lịch sử"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate query is not empty after stripping."""
        if not v.strip():
            raise ValueError("Query không được để trống")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Điều 10 quy định gì về hộ khẩu?",
                "k": 5
            }
        }


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    
    query_id: str
    answer: str
    source_chunks: list
    relevance_scores: list
    processing_time: float
    model: str
    timestamp: str
    conversation_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "123e4567-e89b-12d3-a456-426614174000",
                "answer": "Theo Điều 10, hộ khẩu là...",
                "source_chunks": [
                    {
                        "document_id": "doc_001",
                        "text": "Điều 10. Hộ khẩu...",
                        "similarity_score": 0.95,
                        "chunk_index": 5
                    }
                ],
                "relevance_scores": [0.95, 0.89, 0.85],
                "processing_time": 1.234,
                "model": "gemini-2.0-flash-exp",
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(description="Overall status: healthy, degraded, unhealthy")
    components: Dict[str, Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "components": {
                    "vector_store": {"status": "healthy", "count": 1500},
                    "embedding_service": {"status": "healthy"},
                    "llm_service": {"status": "healthy"},
                    "validator": {"status": "healthy"}
                }
            }
        }


class StatsResponse(BaseModel):
    """Response model for pipeline statistics."""
    
    pipeline_type: str
    retriever_stats: Dict[str, Any]
    validator_enabled: bool
    max_retries: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_type": "hybrid",
                "retriever_stats": {
                    "type": "hybrid",
                    "alpha": 0.6,
                    "min_similarity": 0.7
                },
                "validator_enabled": True,
                "max_retries": 1
            }
        }


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="RAG Query",
    description="Thực hiện truy vấn RAG với hybrid retrieval và output validation"
)
async def query_rag(
    request: QueryRequest,
    pipeline: HybridRAGPipeline = Depends(get_hybrid_pipeline),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """
    Main RAG query endpoint with hybrid retrieval.
    
    Process:
    1. Validate input query
    2. Hybrid retrieval (BM25 + Vector + Rerank)
    3. Generate answer with LLM
    4. Validate output
    5. Return response with sources
    
    Args:
        request: Query request with query text and k value
        pipeline: Injected HybridRAGPipeline dependency
        
    Returns:
        QueryResponse with answer, sources, and metadata
        
    Raises:
        HTTPException 400: Invalid query format
        HTTPException 500: Processing error
    """
    start_time = time.time()

    if request.conversation_id is not None and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập để lưu lịch sử hội thoại",
        )
    
    # Debug logging
    logger.info(
        "Query request received",
        extra={
            "query": request.query,
            "query_length": len(request.query),
            "k": request.k
        }
    )
    
    logger.info(
        "Received RAG query",
        extra={
            "query": request.query[:100],
            "k": request.k
        }
    )
    
    try:
        # Execute pipeline
        rag_response: RAGResponse = pipeline.query(
            query=request.query,
            k=request.k
        )
        
        # Convert to API response format
        response_dict = rag_response.to_dict()

        # Persist the exchange when the caller is authenticated. Anonymous
        # chat remains stateless, preserving the original API behaviour.
        conversation_id: Optional[str] = None
        if user is not None:
            if request.conversation_id is not None:
                conversation = await conversation_repo.get_conversation(
                    db, request.conversation_id, user.id
                )
                if conversation is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Không tìm thấy cuộc hội thoại",
                    )
            else:
                conversation = await conversation_repo.create_conversation(
                    db, user.id, title=request.query[:80]
                )

            await conversation_repo.add_message(
                db, conversation.id, "user", request.query
            )
            await conversation_repo.add_message(
                db,
                conversation.id,
                "assistant",
                rag_response.answer,
                sources=sources_payload(response_dict["source_chunks"]),
            )
            conversation_id = str(conversation.id)

        response_dict["conversation_id"] = conversation_id
        
        # Ensure timestamp is present (defensive check)
        if 'timestamp' not in response_dict:
            from datetime import datetime
            response_dict['timestamp'] = datetime.utcnow().isoformat()
        
        logger.info(
            "RAG query completed successfully",
            extra={
                "query_id": rag_response.query_id,
                "processing_time": rag_response.processing_time,
                "num_sources": len(rag_response.source_chunks)
            }
        )
        
        return QueryResponse(**response_dict)
        
    except RAGValidationError as e:
        # User input validation error
        logger.warning(
            "Query validation failed",
            extra={
                "query": request.query[:100],
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Câu hỏi không hợp lệ: {str(e)}"
        )
        
    except RAGException as e:
        # RAG pipeline error
        logger.error(
            "RAG pipeline error",
            extra={
                "query": request.query[:100],
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi xử lý câu hỏi: {str(e)}"
        )
        
    except Exception as e:
        # Unexpected error
        logger.error(
            "Unexpected error in query endpoint",
            extra={
                "query": request.query[:100],
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi không mong đợi. Vui lòng thử lại sau."
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Kiểm tra trạng thái các thành phần RAG"
)
async def health_check(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
    llm_service: LLMService = Depends(get_llm_service),
    validator: OutputValidator = Depends(get_output_validator)
) -> HealthResponse:
    """
    Health check for all RAG components.
    
    Checks:
    - Vector store connectivity and collection status
    - Embedding service model loaded
    - LLM service connectivity
    - Validator readiness
    
    Returns:
        HealthResponse with status of each component
    """
    logger.info("Health check requested")
    
    components = {}
    all_healthy = True
    
    # Check vector store
    try:
        vector_healthy = vector_store.health_check()
        stats = vector_store.get_collection_stats()
        components["vector_store"] = {
            "status": "healthy" if vector_healthy else "unhealthy",
            "count": stats.get("count", 0),
            "collection": stats.get("name")
        }
        if not vector_healthy:
            all_healthy = False
    except Exception as e:
        components["vector_store"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
    
    # Check embedding service
    try:
        embedding_healthy = embedding_service.health_check()
        components["embedding_service"] = {
            "status": "healthy" if embedding_healthy else "unhealthy",
            "model": embedding_service.MODEL_NAME,
            "dim": embedding_service.EMBEDDING_DIM
        }
        if not embedding_healthy:
            all_healthy = False
    except Exception as e:
        components["embedding_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
    
    # Check LLM service (basic check)
    try:
        components["llm_service"] = {
            "status": "healthy",
            "model": llm_service.MODEL_NAME
        }
    except Exception as e:
        components["llm_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
    
    # Check validator
    try:
        components["validator"] = {
            "status": "healthy",
            "min_evidence_ratio": validator.min_evidence_ratio,
            "strict_mode": validator.strict_mode
        }
    except Exception as e:
        components["validator"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
    
    overall_status = "healthy" if all_healthy else "degraded"
    
    # If critical components fail, mark as unhealthy
    if (components.get("vector_store", {}).get("status") == "unhealthy" or
        components.get("embedding_service", {}).get("status") == "unhealthy"):
        overall_status = "unhealthy"
    
    logger.info(
        "Health check completed",
        extra={
            "overall_status": overall_status,
            "components": list(components.keys())
        }
    )
    
    return HealthResponse(
        status=overall_status,
        components=components
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Pipeline Statistics",
    description="Lấy thông tin cấu hình và thống kê pipeline"
)
async def get_stats(
    pipeline: HybridRAGPipeline = Depends(get_hybrid_pipeline)
) -> StatsResponse:
    """
    Get pipeline statistics and configuration.
    
    Returns:
        StatsResponse with pipeline configuration and metrics
    """
    logger.info("Stats requested")
    
    try:
        stats = pipeline.get_stats()
        
        return StatsResponse(**stats)
        
    except Exception as e:
        logger.error(
            "Failed to get stats",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể lấy thống kê: {str(e)}"
        )
