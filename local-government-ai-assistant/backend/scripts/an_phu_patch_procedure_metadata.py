#!/usr/bin/env python3
"""Patch existing procedure chunks with clean names/citations.

This is a metadata-only migration: embeddings are unchanged. It is safe to
run again after changing the citation format.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import get_vector_store  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.rag.ingestion.procedure_metadata import (  # noqa: E402
    build_procedure_citation,
    clean_procedure_name,
    normalize_for_match,
)
from app.rag.retrieval.index_manager import rebuild_bm25_index  # noqa: E402

DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"


def log(message: str) -> None:
    print(message, flush=True)


def chunked(items: List[Any], size: int) -> List[List[Any]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch procedure metadata")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild-bm25", action="store_true")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    rows = [
        json.loads(line)
        for line in (DATA_DIR / "procedures.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_uuid = {row["uuid"]: row for row in rows}
    vector_store = get_vector_store()
    result = vector_store.collection.get(
        where={"doc_type": "Thủ tục hành chính"},
        include=["metadatas"],
    )

    ids: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    missing = 0
    for chunk_id, metadata in zip(
        result.get("ids") or [],
        result.get("metadatas") or [],
    ):
        metadata = dict(metadata or {})
        document_id = str(metadata.get("document_id") or "")
        uuid = document_id.removeprefix("dvc_procedure_")
        row = by_uuid.get(uuid)
        if not row:
            missing += 1
            continue
        name = clean_procedure_name(row["name"])
        citation = build_procedure_citation(row["name"], row["procedure_id"])
        metadata.update(
            {
                "procedure_id": row["procedure_id"],
                "procedure_name": name,
                "procedure_name_norm": normalize_for_match(name),
                "citation": citation,
                "citation_label": citation,
                "agency": row.get("agency") or "",
                "source_url": row.get("source_url") or "",
            }
        )
        ids.append(chunk_id)
        metadatas.append(metadata)

    log(f"procedure chunks={len(ids)} missing_source={missing}")
    if args.dry_run:
        if ids:
            log(f"sample metadata={json.dumps(metadatas[0], ensure_ascii=False)[:500]}")
        return 0

    for id_batch, metadata_batch in zip(
        chunked(ids, 200),
        chunked(metadatas, 200),
    ):
        vector_store.collection.update(
            ids=id_batch,
            metadatas=metadata_batch,
        )
    log(f"updated={len(ids)}")

    if args.rebuild_bm25:
        log("Rebuilding BM25S index...")
        rebuild_bm25_index(
            vector_store=vector_store,
            persist_dir=settings.bm25s_persist_dir,
            k1=settings.bm25s_k1,
            b=settings.bm25s_b,
        )
        log("BM25S rebuilt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
