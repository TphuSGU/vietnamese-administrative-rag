"""
Document ingestion API.

Provides:
- POST   /api/v1/documents          - Upload a PDF/DOCX/TXT for ingestion
- GET    /api/v1/documents/{job_id} - Check ingestion job status
- GET    /api/v1/documents/stats    - Corpus statistics

Ingestion runs in the background: the endpoint returns a job_id immediately,
then the pipeline chunks/embeds the document, upserts it into ChromaDB and
rebuilds the BM25S derived index so it becomes searchable.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.dependencies import get_vector_store, require_admin
from app.core.logging import get_logger
from app.core.validators import InputValidator
from app.database.vector_store import VectorStore
from app.models.data_models import IngestionStatus
from app.models.db_models import User
from app.models.exceptions import ValidationError
from app.rag.ingestion.pipeline import derive_document_id
from app.rag.retrieval.bm25s_index import BM25SIndex
from app.rag.retrieval.index_manager import rebuild_bm25_index

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# In-memory job registry (single-process deployment; resets on restart).
_ingestion_jobs: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Response Models
# ============================================================================

class DocumentUploadResponse(BaseModel):
    """Response returned immediately after a file is accepted."""

    job_id: str
    document_id: str
    filename: str
    status: str = "pending"
    message: str = "Tài liệu đã được tiếp nhận và đang xử lý"


class IngestionJobResponse(BaseModel):
    """Current state of an ingestion job."""

    job_id: str
    document_id: str
    filename: str
    status: str
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class DocumentStatsResponse(BaseModel):
    """Corpus statistics."""

    collection: str
    chunk_count: int
    bm25_indexed: bool
    bm25_corpus_size: int


class DocumentSummary(BaseModel):
    """One ingested document (aggregated from chunk metadata)."""

    document_id: str
    filename: str
    chunk_count: int


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted_chunks: int


# ============================================================================
# Background processing
# ============================================================================

async def _process_upload(job_id: str, file_path: Path, document_id: str) -> None:
    """Run the ingestion pipeline and rebuild BM25 index in background."""
    job = _ingestion_jobs[job_id]
    job["status"] = IngestionStatus.PROCESSING.value

    try:
        # Imported lazily so the API can start without loading the embedding model.
        from app.core.dependencies import get_ingestion_pipeline

        pipeline = get_ingestion_pipeline()
        result = await pipeline.ingest_document(file_path, document_id=document_id)

        if result.status != IngestionStatus.COMPLETED:
            job["status"] = IngestionStatus.FAILED.value
            job["error_message"] = result.error_message or "Ingestion failed"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            return

        # BM25S has no incremental append: rebuild from ChromaDB (source of truth).
        await asyncio.to_thread(
            rebuild_bm25_index,
            get_vector_store(),
            settings.bm25s_persist_dir,
            settings.bm25s_k1,
            settings.bm25s_b
        )

        job["status"] = IngestionStatus.COMPLETED.value
        job["chunk_count"] = result.chunk_count
        job["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Document ingestion completed",
            extra={
                "job_id": job_id,
                "document_id": document_id,
                "chunk_count": result.chunk_count
            }
        )

    except Exception as exc:
        job["status"] = IngestionStatus.FAILED.value
        job["error_message"] = str(exc)
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.error(
            "Document ingestion failed",
            extra={"job_id": job_id, "document_id": document_id, "error": str(exc)},
            exc_info=True
        )
    finally:
        file_path.unlink(missing_ok=True)


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/stats",
    response_model=DocumentStatsResponse,
    summary="Corpus statistics"
)
async def get_document_stats(
    vector_store: VectorStore = Depends(get_vector_store)
) -> DocumentStatsResponse:
    """Return chunk count and BM25 index status."""
    bm25_stats = BM25SIndex(
        k1=settings.bm25s_k1,
        b=settings.bm25s_b,
        persist_dir=Path(settings.bm25s_persist_dir)
    ).get_stats()

    return DocumentStatsResponse(
        collection=vector_store.COLLECTION_NAME,
        chunk_count=vector_store.count(),
        bm25_indexed=bool(bm25_stats.get("indexed")),
        bm25_corpus_size=int(bm25_stats.get("corpus_size", 0))
    )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for ingestion"
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX hoặc TXT (tối đa 50MB)"),
    _: User = Depends(require_admin),
) -> DocumentUploadResponse:
    """
    Accept a document and ingest it asynchronously.

    Re-uploading the same filename is idempotent: the document_id derived from
    the filename is stable and ChromaDB upserts replace existing chunks.
    """
    filename = file.filename or "upload"

    try:
        sanitized_name = InputValidator.sanitize_filepath(filename)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    content = await file.read()

    try:
        InputValidator.validate_file_upload(sanitized_name, len(content))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content:
        raise HTTPException(status_code=400, detail="File rỗng")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    document_id = derive_document_id(sanitized_name)
    stored_path = upload_dir / f"{job_id}_{sanitized_name}"

    try:
        stored_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể lưu file tạm: {exc}"
        ) from exc

    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "document_id": document_id,
        "filename": sanitized_name,
        "status": IngestionStatus.PENDING.value,
        "chunk_count": 0,
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(_process_upload, job_id, stored_path, document_id)

    logger.info(
        "Document upload accepted",
        extra={
            "job_id": job_id,
            "document_id": document_id,
            "file_name": sanitized_name,
            "size_bytes": len(content)
        }
    )

    return DocumentUploadResponse(
        job_id=job_id,
        document_id=document_id,
        filename=sanitized_name
    )


@router.get(
    "",
    response_model=list[DocumentSummary],
    summary="List ingested documents (admin)"
)
async def list_documents(
    _: User = Depends(require_admin),
    vector_store: VectorStore = Depends(get_vector_store),
) -> list[DocumentSummary]:
    """Aggregate chunk metadata into one row per document."""
    return [
        DocumentSummary(**row) for row in vector_store.list_documents()
    ]


@router.delete(
    "/{document_id}",
    response_model=DeleteDocumentResponse,
    summary="Delete a document and rebuild BM25 (admin)"
)
async def delete_document(
    document_id: str,
    _: User = Depends(require_admin),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DeleteDocumentResponse:
    """Delete all chunks of a document, then refresh the derived BM25 index."""
    deleted = vector_store.delete_document(document_id)
    if deleted == 0:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy tài liệu"
        )

    await asyncio.to_thread(
        rebuild_bm25_index,
        vector_store,
        settings.bm25s_persist_dir,
        settings.bm25s_k1,
        settings.bm25s_b,
    )
    return DeleteDocumentResponse(
        document_id=document_id, deleted_chunks=deleted
    )


@router.get(
    "/{job_id}",
    response_model=IngestionJobResponse,
    summary="Check ingestion job status"
)
async def get_ingestion_job(job_id: str) -> IngestionJobResponse:
    """Return the status of an ingestion job (in-memory, single process)."""
    job = _ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy job")

    return IngestionJobResponse(**job)
