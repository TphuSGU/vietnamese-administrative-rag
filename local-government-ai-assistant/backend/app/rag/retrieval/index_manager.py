"""
Derived-index management for hybrid retrieval.

ChromaDB is the source of truth for chunks and embeddings. BM25S does not
support incremental append, so its index is rebuilt from the stored chunks
whenever a document is ingested. Rebuilding only re-tokenizes existing text;
documents are never re-parsed and embeddings are never recomputed.
"""

import shutil
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger
from app.database.vector_store import VectorStore
from app.models.data_models import RetrievedChunk
from app.rag.retrieval.bm25s_index import BM25SIndex

logger = get_logger(__name__)


def load_all_chunks(vector_store: VectorStore) -> List[RetrievedChunk]:
    """
    Load every stored chunk from ChromaDB.

    Args:
        vector_store: Vector store holding the chunks

    Returns:
        Chunks sorted by (document_id, chunk_index) for deterministic rebuilds
    """
    result = vector_store.collection.get(include=["documents", "metadatas"])

    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    chunks: List[RetrievedChunk] = []
    for text, metadata in zip(documents, metadatas):
        if not text:
            continue
        chunks.append(
            RetrievedChunk(
                text=text,
                # Similarity is irrelevant for BM25; RRF overwrites it later.
                similarity_score=0.0,
                metadata=metadata or {}
            )
        )

    chunks.sort(key=lambda chunk: (chunk.document_id, chunk.chunk_index))
    return chunks


def reset_bm25_index(persist_dir: str | Path) -> None:
    """Delete the persisted BM25S index directory (no-op if absent)."""
    path = Path(persist_dir)
    if path.exists():
        shutil.rmtree(path)
        logger.warning("BM25S index removed", extra={"persist_dir": str(path)})


def rebuild_bm25_index(
    vector_store: VectorStore,
    persist_dir: str | Path = "./bm25s_index",
    k1: float = 1.5,
    b: float = 0.75
) -> Optional[BM25SIndex]:
    """
    Rebuild and persist the BM25S index from all chunks stored in ChromaDB.

    Args:
        vector_store: Vector store acting as source of truth
        persist_dir: Directory where the BM25S index is persisted
        k1: BM25 term-frequency saturation parameter
        b: BM25 length-normalization parameter

    Returns:
        The rebuilt BM25SIndex, or None when there are no chunks
    """
    chunks = load_all_chunks(vector_store)

    if not chunks:
        reset_bm25_index(persist_dir)
        logger.warning("No chunks found; BM25S index not built")
        return None

    index = BM25SIndex(k1=k1, b=b, persist_dir=Path(persist_dir))
    index.index_chunks(chunks)

    logger.info(
        "BM25S index rebuilt from vector store",
        extra={
            "chunk_count": len(chunks),
            "persist_dir": str(persist_dir)
        }
    )
    return index
