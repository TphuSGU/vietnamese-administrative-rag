"""
FastAPI application for Local Government AI Assistant - RAG API.

Main application that includes:
- Chat API endpoints for RAG queries
- CORS middleware for frontend access
- Automatic API documentation
- Startup/shutdown event handlers
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.core.logging import get_logger
from app.core.config import settings, validate_configuration
from app.core.dependencies import (
    get_embedding_service,
    get_vector_store,
    get_llm_service
)

logger = get_logger(__name__)


# ============================================================================
# Lifespan Context Manager for Startup/Shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles:
    - Startup: Initialize heavy components, validate configuration
    - Shutdown: Cleanup resources
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Local Government AI Assistant - RAG API")
    logger.info("=" * 60)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        validate_configuration(settings)
        logger.info("✓ Configuration valid")
        
        # Initialize singleton services (cached by lru_cache)
        logger.info("Initializing services...")
        
        embedding_service = get_embedding_service()
        logger.info("✓ Embedding service ready")
        
        vector_store = get_vector_store()
        logger.info("✓ Vector store ready")
        
        llm_service = get_llm_service()
        logger.info("✓ LLM service ready")
        
        # Health checks
        logger.info("Running health checks...")
        if not embedding_service.health_check():
            logger.warning("⚠ Embedding service health check failed")
        else:
            logger.info("✓ Embedding service healthy")
        
        if not vector_store.health_check():
            logger.warning("⚠ Vector store health check failed")
        else:
            logger.info("✓ Vector store healthy")
        
        logger.info("=" * 60)
        logger.info("RAG API started successfully")
        logger.info(f"API Host: {settings.api_host}:{settings.api_port}")
        logger.info(f"Docs: http://{settings.api_host}:{settings.api_port}/docs")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG API...")
    logger.info("✓ Shutdown complete")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Local Government AI Assistant - RAG API",
    version="1.0.0",
    description=(
        "Vietnamese document RAG system with hybrid retrieval.\n\n"
        "Features:\n"
        "- Hybrid search (BM25 + Vector + Reranking)\n"
        "- Gemini LLM for answer generation\n"
        "- Output validation to prevent hallucination\n"
        "- Vietnamese language support"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(chat_router)


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get(
    "/",
    summary="Root",
    description="API status check"
)
async def root():
    """Root endpoint - returns API status."""
    return {
        "status": "ok",
        "service": "Local Government AI Assistant - RAG API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
            "error_type": type(exc).__name__
        }
    )


# ============================================================================
# Run Application (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
