#!/usr/bin/env python3
"""Ingest filtered HF legal documents into Chroma + BM25.

Usage:
    python scripts/hf_legal_ingest.py --limit 20 --dry-run
    python scripts/hf_legal_ingest.py --limit 500
    python scripts/hf_legal_ingest.py --no-rebuild-bm25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Set

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import get_embedding_service, get_vector_store  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.models.data_models import Document  # noqa: E402
from app.rag.ingestion.chunker import SemanticChunker  # noqa: E402
from app.rag.ingestion.citation import build_chunk_citation  # noqa: E402
from app.rag.ingestion.legal_structure import annotate_chunks  # noqa: E402
from app.rag.retrieval.index_manager import rebuild_bm25_index  # noqa: E402

DATA_DIR = BACKEND_DIR / "data" / "legal_hf"
DOCUMENTS_PATH = DATA_DIR / "hf_documents.jsonl"
REPORT_PATH = DATA_DIR / "hf_ingest_report.json"


def log(message: str) -> None:
    print(message, flush=True)


def iter_documents(limit: int = 0, offset: int = 0) -> Iterator[Dict[str, Any]]:
    seen = 0
    emitted = 0
    with DOCUMENTS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            if seen < offset:
                seen += 1
                continue
            seen += 1
            yield json.loads(line)
            emitted += 1
            if limit and emitted >= limit:
                break


def existing_document_ids(vector_store: Any) -> Set[str]:
    try:
        result = vector_store.collection.get(
            where={"corpus": "hf_legal"},
            include=["metadatas"],
        )
    except Exception:
        return set()
    return {
        str(metadata.get("document_id"))
        for metadata in result.get("metadatas") or []
        if metadata and metadata.get("document_id")
    }


def build_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    doc_id = row["doc_id"]
    return {
        "document_id": doc_id,
        "doc_id": doc_id,
        "corpus": "hf_legal",
        "doc_scope": row.get("doc_scope") or "",
        "doc_number": row.get("so_ky_hieu") or "",
        "doc_type": row.get("loai_van_ban") or "",
        "issued_date": row.get("issued_date") or "",
        "effective_date": row.get("effective_date") or "",
        "issuer": row.get("co_quan_ban_hanh") or "",
        "citation_label": row.get("citation_label") or "",
        "title": row.get("title") or "",
        "linh_vuc": row.get("linh_vuc") or "",
        "nganh": row.get("nganh") or "",
        "text_source": "hf",
        "source_url": "",
    }


def chunk_row(row: Dict[str, Any], chunker: SemanticChunker) -> List[Any]:
    text = str(row.get("text") or "")
    doc = Document(
        id=row["doc_id"],
        text=text,
        filename=f"{row['doc_id']}.txt",
        file_size=len(text.encode("utf-8")),
        upload_timestamp=datetime.now(timezone.utc),
        format="txt",
    )
    chunks = chunker.chunk_document(doc)
    if not chunks:
        return []
    metadata = build_metadata(row)
    annotate_chunks(chunks, text)
    for chunk in chunks:
        chunk.metadata.update(metadata)
        chunk.metadata["citation"] = build_chunk_citation(
            {**metadata, **chunk.metadata}
        )
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest filtered HF legal docs")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-rebuild-bm25", action="store_true")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    chunker = SemanticChunker(settings.chunk_min_size, settings.chunk_max_size)
    vector_store = get_vector_store()
    existing = set() if args.dry_run else existing_document_ids(vector_store)
    log(f"[resume] existing hf docs={len(existing)}")

    embedding_service = None if args.dry_run else get_embedding_service()
    processed = 0
    skipped = 0
    chunks_total = 0
    chars_total = 0
    started = time.time()

    for row in iter_documents(args.limit, args.offset):
        doc_id = row["doc_id"]
        if doc_id in existing:
            skipped += 1
            continue
        chunks = chunk_row(row, chunker)
        if not chunks:
            log(f"[skip] {doc_id}: no chunks")
            continue
        if args.dry_run:
            processed += 1
            chunks_total += len(chunks)
            chars_total += len(row.get("text") or "")
            if processed % 25 == 0:
                log(
                    f"[dry-run] docs={processed} chunks={chunks_total} "
                    f"avg_chunks={chunks_total / processed:.1f}"
                )
            continue

        embeddings = embedding_service.embed_chunks(chunks)
        # Resume skips existing IDs above; a new doc has no old chunks to delete.
        vector_store.add_chunks(
            chunks,
            embeddings,
            filename=f"{doc_id}.txt",
            extra_metadata=build_metadata(row),
        )
        processed += 1
        chunks_total += len(chunks)
        chars_total += len(row.get("text") or "")
        if processed % 25 == 0:
            elapsed = max(time.time() - started, 0.001)
            log(
                f"[ingest] docs={processed} skipped={skipped} chunks={chunks_total} "
                f"chars={chars_total} chunks/s={chunks_total / elapsed:.1f}"
            )

    elapsed = time.time() - started
    if args.dry_run:
        avg = chunks_total / processed if processed else 0
        estimated_seconds = chunks_total / 5.0
        log(
            f"[dry-run] docs={processed} chunks={chunks_total} "
            f"avg_chunks={avg:.1f} est_embed_hours={estimated_seconds / 3600:.2f}"
        )
        return 0

    if not args.no_rebuild_bm25:
        log("Rebuilding BM25S index...")
        rebuild_bm25_index(
            vector_store=vector_store,
            persist_dir=settings.bm25s_persist_dir,
            k1=settings.bm25s_k1,
            b=settings.bm25s_b,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents_processed": processed,
        "documents_skipped": skipped,
        "chunks_added": chunks_total,
        "chars_processed": chars_total,
        "elapsed_seconds": round(elapsed, 2),
        "chunks_per_second": round(chunks_total / elapsed, 2) if elapsed else 0,
        "collection": vector_store.get_collection_stats(),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
