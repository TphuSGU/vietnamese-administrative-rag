#!/usr/bin/env python3
"""
Ingest documents into ChromaDB and rebuild the BM25S derived index.

ChromaDB is the source of truth. After ingestion the BM25S index is rebuilt
from every stored chunk (a few seconds for a small corpus), so newly uploaded
documents immediately become searchable by the hybrid retriever.

Usage:
    python scripts/ingest.py                      # ingest data/raw
    python scripts/ingest.py --path data/raw/150-2025-ND-CP.pdf
    python scripts/ingest.py --reset              # clean seed
    python scripts/ingest.py --no-rebuild-bm25
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import (  # noqa: E402
    get_ingestion_pipeline,
    get_vector_store,
)
from app.core.logging import setup_logging  # noqa: E402
from app.models.data_models import IngestionStatus  # noqa: E402
from app.rag.ingestion.pipeline import derive_document_id  # noqa: E402
from app.rag.retrieval.index_manager import (  # noqa: E402
    rebuild_bm25_index,
    reset_bm25_index,
)

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


def make_document_id(path: Path) -> str:
    """Derive a stable document ID from the filename."""
    return derive_document_id(path.name)


def collect_documents(target: Path) -> List[Path]:
    """Collect supported document files from a file or directory."""
    if target.is_file():
        if target.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported document: {target}")
        return [target]

    if not target.exists():
        raise ValueError(f"Path does not exist: {target}")

    files = sorted(
        path for path in target.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    return files


async def ingest_all(paths: List[Path]) -> int:
    pipeline = get_ingestion_pipeline()
    failures = 0

    for index, path in enumerate(paths, 1):
        document_id = make_document_id(path)
        print(f"\n[{index}/{len(paths)}] {path.name} -> document_id={document_id}")

        result = await pipeline.ingest_document(path, document_id=document_id)

        status = result.status.value if hasattr(result.status, "value") else result.status
        print(f"    status={status} chunks={result.chunk_count} job={result.job_id}")
        if result.error_message:
            print(f"    error: {result.error_message}")

        if result.status != IngestionStatus.COMPLETED:
            failures += 1

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents for RAG")
    parser.add_argument(
        "--path",
        type=Path,
        default=BACKEND_DIR / "data" / "raw",
        help="File or directory to ingest (default: data/raw)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear ChromaDB collection and BM25S index before ingesting"
    )
    parser.add_argument(
        "--no-rebuild-bm25",
        action="store_true",
        help="Skip BM25S rebuild after ingestion"
    )
    args = parser.parse_args()

    setup_logging(settings.log_level)

    paths = collect_documents(args.path)
    if not paths:
        print(f"No supported documents found in {args.path}")
        return 1

    vector_store = get_vector_store()

    if args.reset:
        print("Resetting indexes...")
        vector_store.clear_collection()
        reset_bm25_index(settings.bm25s_persist_dir)

    print(f"Ingesting {len(paths)} document(s) from {args.path}")
    failures = asyncio.run(ingest_all(paths))

    if not args.no_rebuild_bm25:
        print("\nRebuilding BM25S index from stored chunks...")
        bm25_index = rebuild_bm25_index(
            vector_store=vector_store,
            persist_dir=settings.bm25s_persist_dir,
            k1=settings.bm25s_k1,
            b=settings.bm25s_b,
        )
        if bm25_index:
            print(f"    BM25S: {bm25_index.get_stats()}")

    stats = vector_store.get_collection_stats()
    print("\n" + "=" * 60)
    print(f"ChromaDB: collection={stats.get('name')} chunks={stats.get('count')}")
    print(f"BM25S dir: {settings.bm25s_persist_dir}")
    print(f"Failed documents: {failures}")
    print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
