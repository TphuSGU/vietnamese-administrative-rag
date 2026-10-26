"""
Document Ingestion Pipeline Orchestration.
Orchestrates: Loader → Cleaner → Chunker → Embedder → Storage
Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

from pathlib import Path
import re
import uuid
import asyncio
from typing import Optional, Dict
from datetime import datetime

from app.rag.ingestion.loader import DocumentLoader
from app.rag.ingestion.cleaner import TextCleaner
from app.rag.ingestion.chunker import SemanticChunker
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.core.logging import get_logger
from app.models.data_models import IngestionStatus, IngestionResult
from app.models.exceptions import RAGException

logger = get_logger(__name__)


def derive_document_id(filename: str) -> str:
    """
    Derive a stable, filesystem-safe document ID from a filename.

    Example: "150-2025-ND-CP.pdf" -> "150-2025-ND-CP"

    Using a stable ID makes re-ingestion idempotent: chunk IDs are
    ``{document_id}_{chunk_index}`` and ChromaDB upserts replace them.
    """
    stem = Path(filename).stem.strip()
    doc_id = re.sub(r"[^\w.-]+", "-", stem, flags=re.UNICODE).strip("-._")
    return doc_id or "document"


class IngestionError(RAGException):
    """Custom exception for ingestion failures."""
    pass


class IngestionJob:
    """Ingestion job tracker."""
    
    def __init__(self, job_id: str, document_path: str):
        self.job_id = job_id
        self.document_path = document_path
        self.status = IngestionStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.chunk_count: int = 0
        self.document_id: Optional[str] = None


class IngestionStatusTracker:
    """Thread-safe status tracker for ingestion jobs."""
    
    def __init__(self):
        self._jobs: Dict[str, IngestionJob] = {}
        self._lock = asyncio.Lock()
    
    async def create_job(self, job_id: str, document_path: str) -> IngestionJob:
        """Create new job with PENDING status."""
        async with self._lock:
            job = IngestionJob(job_id=job_id, document_path=document_path)
            self._jobs[job_id] = job
            return job
    
    async def update_status(
        self, 
        job_id: str, 
        status: IngestionStatus,
        **kwargs
    ) -> None:
        """Update job status with additional fields."""
        async with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = status
                
                if status == IngestionStatus.PROCESSING:
                    job.started_at = datetime.utcnow()
                elif status in [IngestionStatus.COMPLETED, IngestionStatus.FAILED]:
                    job.completed_at = datetime.utcnow()
                
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
    
    async def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """Get job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)


class DocumentIngestionPipeline:
    """
    Orchestrates complete document ingestion pipeline.
    
    Stages:
    1. Load document (PDF/DOCX/TXT)
    2. Clean text
    3. Semantic chunking
    4. Generate embeddings
    5. Store in vector database
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    
    MAX_CONCURRENT_PIPELINES = 4
    
    def __init__(
        self,
        loader: DocumentLoader,
        cleaner: TextCleaner,
        chunker: SemanticChunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        self.loader = loader
        self.cleaner = cleaner
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        
        self.status_tracker = IngestionStatusTracker()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PIPELINES)
        
        logger.info("DocumentIngestionPipeline initialized")
    
    async def ingest_document(
        self, 
        file_path: Path,
        document_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Ingest a document through the complete pipeline.
        
        Args:
            file_path: Path to document (PDF/DOCX/TXT)
            document_id: Optional stable document ID (e.g. "150-2025-ND-CP").
                         If omitted a random ID is generated.
            
        Returns:
            IngestionResult with job_id, status, chunk_count, document_id
            
        Validates: Requirements 6.1, 6.2, 6.3, 6.4
        """
        # Generate job ID
        job_id = str(uuid.uuid4())
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:8]}"
        
        # Create job tracking
        await self.status_tracker.create_job(job_id, str(file_path))
        
        # Acquire semaphore for concurrency control (Req 6.4)
        async with self._semaphore:
            try:
                # Update status to PROCESSING
                await self.status_tracker.update_status(
                    job_id, 
                    IngestionStatus.PROCESSING,
                    document_id=document_id
                )
                
                logger.info(
                    f"Starting ingestion",
                    extra={
                        "job_id": job_id,
                        "document_id": document_id,
                        "file_path": str(file_path)
                    }
                )
                
                # Stage 1: Load document
                try:
                    document = self.loader.load_document(file_path=str(file_path), document_id=document_id)
                    logger.info(f"Stage 1 complete: Document loaded", extra={"job_id": job_id})
                except Exception as e:
                    raise IngestionError(f"Stage 1 (Load) failed: {e}")
                
                # Stage 2: Clean text
                try:
                    cleaned_text = self.cleaner.clean(document.text)
                    document.text = cleaned_text
                    logger.info(f"Stage 2 complete: Text cleaned", extra={"job_id": job_id})
                except Exception as e:
                    raise IngestionError(f"Stage 2 (Clean) failed: {e}")
                
                # Stage 3: Chunk document
                try:
                    chunks = self.chunker.chunk_document(document)
                    if not chunks:
                        raise IngestionError("No chunks generated from document")
                    logger.info(
                        f"Stage 3 complete: Generated {len(chunks)} chunks",
                        extra={"job_id": job_id, "chunk_count": len(chunks)}
                    )
                except Exception as e:
                    raise IngestionError(f"Stage 3 (Chunk) failed: {e}")
                
                # Stage 4: Generate embeddings
                try:
                    embeddings = self.embedding_service.embed_chunks(chunks)
                    logger.info(
                        f"Stage 4 complete: Embeddings generated",
                        extra={"job_id": job_id, "embedding_shape": embeddings.shape}
                    )
                except Exception as e:
                    raise IngestionError(f"Stage 4 (Embed) failed: {e}")
                
                # Stage 5: Store in vector DB
                try:
                    self.vector_store.add_chunks(
                        chunks, embeddings, filename=document.filename
                    )
                    logger.info(
                        f"Stage 5 complete: Chunks stored",
                        extra={"job_id": job_id, "chunk_count": len(chunks)}
                    )
                except Exception as e:
                    raise IngestionError(f"Stage 5 (Store) failed: {e}")
                
                # Mark as completed
                await self.status_tracker.update_status(
                    job_id,
                    IngestionStatus.COMPLETED,
                    chunk_count=len(chunks)
                )
                
                logger.info(
                    f"Ingestion completed successfully",
                    extra={
                        "job_id": job_id,
                        "document_id": document_id,
                        "chunk_count": len(chunks)
                    }
                )
                
                return IngestionResult(
                    job_id=job_id,
                    status=IngestionStatus.COMPLETED,
                    chunk_count=len(chunks),
                    document_id=document_id
                )
                
            except Exception as e:
                # Mark as failed
                await self.status_tracker.update_status(
                    job_id,
                    IngestionStatus.FAILED,
                    error=str(e)
                )
                
                logger.error(
                    f"Ingestion failed",
                    extra={
                        "job_id": job_id,
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                
                return IngestionResult(
                    job_id=job_id,
                    status=IngestionStatus.FAILED,
                    chunk_count=0,
                    document_id=document_id,
                    error_message=str(e)
                )
    
    async def get_status(self, job_id: str) -> Optional[IngestionJob]:
        """Get job status by ID."""
        return await self.status_tracker.get_job(job_id)
    
    async def get_result(self, job_id: str) -> Optional[IngestionResult]:
        """Get final result for completed job."""
        job = await self.status_tracker.get_job(job_id)
        if not job:
            return None
        
        return IngestionResult(
            job_id=job.job_id,
            status=job.status,
            chunk_count=job.chunk_count,
            document_id=job.document_id,
            error_message=job.error
        )
