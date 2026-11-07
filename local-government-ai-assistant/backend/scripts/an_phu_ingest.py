#!/usr/bin/env python3
"""Ingest An Phu manual text into ChromaDB and rebuild BM25S.

The text files are the source of truth after manual correction. Each document
gets locality/document metadata on every chunk, including ``citation_label`` so
the generation prompt can cite the real document number instead of the
internal ``document_id``.

Usage:
    python scripts/an_phu_ingest.py --dry-run
    python scripts/an_phu_ingest.py
    python scripts/an_phu_ingest.py --doc an_phu_2466 an_phu_2796
    python scripts/an_phu_ingest.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import (  # noqa: E402
    get_embedding_service,
    get_vector_store,
)
from app.core.logging import setup_logging  # noqa: E402
from app.models.data_models import Document  # noqa: E402
from app.rag.ingestion.chunker import SemanticChunker  # noqa: E402
from app.rag.ingestion.citation import build_chunk_citation  # noqa: E402
from app.rag.ingestion.legal_structure import annotate_chunks  # noqa: E402
from app.rag.retrieval.index_manager import rebuild_bm25_index  # noqa: E402

DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"
DEFAULT_MANIFEST = DATA_DIR / "manifest.json"
DEFAULT_REPORT = DATA_DIR / "ingest_report.json"
LOCALITY_CODE = "25975"
LOCALITY_SLUG = "an_phu"
LOCALITY_NAME = "Phường An Phú"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(message, flush=True)


def normalize_text(text: str) -> str:
    """NFC + stable whitespace, preserving table rows as separate paragraphs."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: List[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            lines.append("")
        elif "|" in line:
            # One table row per paragraph; the chunker merges rows up to
            # max_size, which keeps rows intact instead of splitting cells.
            lines.extend([line, ""])
        else:
            lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_date(iso_date: str) -> str:
    try:
        year, month, day = iso_date.split("-")
        return f"{int(day)}/{int(month)}/{year}"
    except (AttributeError, ValueError):
        return iso_date or ""


def build_citation_label(document: Dict[str, Any]) -> str:
    label = (document.get("citation_label") or "").strip()
    if label:
        return label
    doc_type = document.get("doc_type") or "Văn bản"
    doc_number = document.get("doc_number") or ""
    issued_date = format_date(document.get("issued_date") or "")
    issuer = document.get("issuer") or LOCALITY_NAME
    return f"{doc_type} số {doc_number} ngày {issued_date} của {issuer}"


def build_metadata(document: Dict[str, Any]) -> Dict[str, Any]:
    """Document-level metadata copied to every chunk."""
    return {
        "document_id": document["doc_id"],
        "doc_id": document["doc_id"],
        "portal_id": int(document.get("portal_id") or 0),
        "locality_code": LOCALITY_CODE,
        "locality_slug": LOCALITY_SLUG,
        "locality_name": LOCALITY_NAME,
        "corpus": "an_phu_legal",
        "doc_scope": "local",
        "doc_number": document.get("doc_number") or "",
        "doc_type": document.get("doc_type") or "",
        "issued_date": document.get("issued_date") or "",
        "effective_date": document.get("effective_date") or "",
        "issuer": document.get("issuer") or "",
        "citation_label": build_citation_label(document),
        "source_url": document.get("source_url") or "",
        "text_source": document.get("text_source") or "",
        "page_count": int(document.get("page_count") or 0),
        "pdf_count": int(document.get("pdf_count") or 0),
        "title": document.get("title") or "",
    }


def load_documents(
    manifest_path: Path,
    selected: Optional[set[str]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = []
    for document in manifest.get("documents") or []:
        doc_id = document.get("doc_id") or ""
        if selected and doc_id not in selected:
            continue
        text_path = DATA_DIR / (document.get("text_path") or "")
        if not text_path.is_file() or document.get("ocr_status") == "missing_pdf":
            log(f"[skip] {doc_id}: no text file")
            continue
        if limit and len(documents) >= limit:
            break
        documents.append(document)
    return documents


def ingest_document(
    document: Dict[str, Any],
    *,
    chunker: SemanticChunker,
    embedding_service: Any,
    vector_store: Any,
    dry_run: bool,
) -> Dict[str, Any]:
    doc_id = document["doc_id"]
    text_path = DATA_DIR / document["text_path"]
    raw_text = text_path.read_text(encoding="utf-8")
    text = normalize_text(raw_text)

    doc = Document(
        id=doc_id,
        text=text,
        filename=text_path.name,
        file_size=len(text.encode("utf-8")),
        upload_timestamp=datetime.now(timezone.utc),
        format="txt",
    )
    chunks = chunker.chunk_document(doc)
    if not chunks:
        raise RuntimeError("no chunks generated")

    document_metadata = build_metadata(document)
    annotate_chunks(chunks, text)
    for chunk in chunks:
        chunk.metadata["citation"] = build_chunk_citation(
            {**document_metadata, **chunk.metadata}
        )

    if dry_run:
        sizes = [chunk.length for chunk in chunks]
        return {
            "doc_id": doc_id,
            "status": "dry_run",
            "chars": len(raw_text),
            "chunks": len(chunks),
            "min_chunk": min(sizes),
            "max_chunk": max(sizes),
            "table_chunks": sum(1 for chunk in chunks if "|" in chunk.text),
            "article_chunks": sum(1 for chunk in chunks if chunk.metadata.get("article_no")),
        }

    embeddings = embedding_service.embed_chunks(chunks)
    # Remove old chunks first so re-ingestion cannot leave stale tail chunks.
    vector_store.delete_document(doc_id)
    vector_store.add_chunks(
        chunks,
        embeddings,
        filename=text_path.name,
        extra_metadata=document_metadata,
    )
    sizes = [chunk.length for chunk in chunks]
    return {
        "doc_id": doc_id,
        "status": "done",
        "chars": len(raw_text),
        "chunks": len(chunks),
        "min_chunk": min(sizes),
        "max_chunk": max(sizes),
        "table_chunks": sum(1 for chunk in chunks if "|" in chunk.text),
        "article_chunks": sum(1 for chunk in chunks if chunk.metadata.get("article_no")),
        "citation_label": build_citation_label(document),
        "completed_at": utc_now(),
    }


def build_report_from_store(
    documents: List[Dict[str, Any]],
    vector_store: Any,
) -> List[Dict[str, Any]]:
    """Rebuild the report from Chroma chunks without re-embedding."""
    stored = vector_store.collection.get(
        where={"locality_slug": LOCALITY_SLUG},
        include=["metadatas"],
    )
    counts: Dict[str, int] = {}
    article_counts: Dict[str, int] = {}
    for metadata in stored.get("metadatas") or []:
        if not metadata:
            continue
        doc_id = metadata.get("document_id")
        if not doc_id:
            continue
        counts[doc_id] = counts.get(doc_id, 0) + 1
        if metadata.get("article_no"):
            article_counts[doc_id] = article_counts.get(doc_id, 0) + 1

    results = []
    for document in documents:
        doc_id = document["doc_id"]
        text_path = DATA_DIR / document["text_path"]
        results.append(
            {
                "doc_id": doc_id,
                "status": "done" if counts.get(doc_id) else "missing_chunks",
                "chars": len(text_path.read_text(encoding="utf-8")),
                "chunks": counts.get(doc_id, 0),
                "article_chunks": article_counts.get(doc_id, 0),
                "citation_label": build_citation_label(document),
            }
        )
    return results


def write_report(report_path: Path, results: List[Dict[str, Any]]) -> None:
    report = {
        "generated_at": utc_now(),
        "locality_code": LOCALITY_CODE,
        "locality_slug": LOCALITY_SLUG,
        "documents": len(results),
        "chunks": sum(int(r.get("chunks") or 0) for r in results),
        "chars": sum(int(r.get("chars") or 0) for r in results),
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest An Phu text for RAG")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--doc", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--no-rebuild-bm25", action="store_true")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    documents = load_documents(
        args.manifest,
        selected=set(args.doc) if args.doc else None,
        limit=args.limit,
    )
    if not documents:
        log("Không có văn bản nào để ingest.")
        return 1

    if args.report_only:
        vector_store = get_vector_store()
        results = build_report_from_store(documents, vector_store)
        write_report(args.report, results)
        log(f"Report rebuilt: {args.report}")
        log(f"Documents: {len(results)} | chunks: {sum(r['chunks'] for r in results)}")
        return 0

    chunker = SemanticChunker(
        min_size=settings.chunk_min_size,
        max_size=settings.chunk_max_size,
    )
    vector_store = get_vector_store()
    embedding_service = None if args.dry_run else get_embedding_service()

    log(
        f"Ingest {len(documents)} văn bản | chunk={settings.chunk_min_size}-"
        f"{settings.chunk_max_size} | dry_run={args.dry_run}"
    )
    results: List[Dict[str, Any]] = []
    for index, document in enumerate(documents, 1):
        doc_id = document["doc_id"]
        log(f"\n[{index}/{len(documents)}] {doc_id} ({document.get('doc_number', '')})")
        try:
            result = ingest_document(
                document,
                chunker=chunker,
                embedding_service=embedding_service,
                vector_store=vector_store,
                dry_run=args.dry_run,
            )
            results.append(result)
            log(
                f"  {result['status']}: chunks={result['chunks']} "
                f"min={result['min_chunk']} max={result['max_chunk']} "
                f"table_chunks={result['table_chunks']} "
                f"article_chunks={result.get('article_chunks', 0)}"
            )
        except Exception as exc:
            log(f"  [error] {exc}")
            results.append(
                {
                    "doc_id": doc_id,
                    "status": "failed",
                    "error": str(exc),
                    "chars": len((DATA_DIR / document["text_path"]).read_text(encoding="utf-8")),
                    "chunks": 0,
                }
            )
        write_report(args.report, results)

    if not args.dry_run and not args.no_rebuild_bm25:
        log("\nRebuilding BM25S index from all stored chunks...")
        index = rebuild_bm25_index(
            vector_store=vector_store,
            persist_dir=settings.bm25s_persist_dir,
            k1=settings.bm25s_k1,
            b=settings.bm25s_b,
        )
        if index:
            log(f"  BM25S: {index.get_stats()}")

    failed = [r for r in results if r.get("status") == "failed"]
    stats = vector_store.get_collection_stats()
    log("\n" + "=" * 64)
    log(f"Documents: {len(results)} | failed: {len(failed)}")
    log(f"Chunks: {sum(int(r.get('chunks') or 0) for r in results):,}")
    log(f"ChromaDB: {stats}")
    log(f"Report: {args.report}")
    log("=" * 64)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
