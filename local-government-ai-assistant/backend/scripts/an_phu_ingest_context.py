#!/usr/bin/env python3
"""Ingest An Phu profile, work schedules, and DVC procedures."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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
from app.rag.ingestion.procedure_metadata import (  # noqa: E402
    build_procedure_citation,
    clean_procedure_name,
    normalize_for_match,
    normalize_procedure_text,
)
from app.rag.retrieval.index_manager import rebuild_bm25_index  # noqa: E402

DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"
REPORT_PATH = DATA_DIR / "context_ingest_report.json"
LOCALITY_CODE = "25975"
LOCALITY_NAME = "Phường An Phú"


def log(message: str) -> None:
    print(message, flush=True)


def base_metadata(doc_id: str, doc_type: str, citation: str, **extra: Any) -> Dict[str, Any]:
    metadata = {
        "document_id": doc_id,
        "doc_id": doc_id,
        "locality_code": LOCALITY_CODE,
        "locality_slug": "an_phu",
        "locality_name": LOCALITY_NAME,
        "doc_scope": "local",
        "doc_type": doc_type,
        "citation_label": citation,
        "citation": citation,
        "text_source": "portal/dvc",
        "filename": f"{doc_id}.txt",
    }
    metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata


def ingest_one(
    doc_id: str,
    text: str,
    metadata: Dict[str, Any],
    chunker: SemanticChunker,
    embedding_service: Any,
    vector_store: Any,
    replace: bool = True,
) -> int:
    document = Document(
        id=doc_id,
        text=text,
        filename=f"{doc_id}.txt",
        file_size=len(text.encode("utf-8")),
        upload_timestamp=datetime.now(timezone.utc),
        format="txt",
    )
    chunks = chunker.chunk_document(document)
    if not chunks:
        raise RuntimeError("no chunks generated")
    for chunk in chunks:
        chunk.metadata.update(metadata)
        chunk.metadata["citation"] = metadata["citation"]
    embeddings = embedding_service.embed_chunks(chunks)
    if replace:
        vector_store.delete_document(doc_id)
    vector_store.add_chunks(
        chunks,
        embeddings,
        filename=metadata.get("filename") or f"{doc_id}.txt",
        extra_metadata=metadata,
    )
    return len(chunks)


def load_existing_doc_ids(vector_store: Any) -> set[str]:
    result = vector_store.collection.get(
        where={"doc_scope": "local"},
        include=["metadatas"],
    )
    return {
        str(metadata.get("document_id"))
        for metadata in result.get("metadatas") or []
        if metadata and metadata.get("document_id")
    }


def load_profile_text() -> str:
    path = DATA_DIR / "profile.yaml"
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    locality = data.get("locality") or {}
    contact = data.get("contact") or {}
    hours = data.get("working_hours") or {}
    lines = [
        f"Địa phương: {locality.get('name', LOCALITY_NAME)}",
        f"Mã địa phương: {locality.get('code', LOCALITY_CODE)}",
        f"Cấp: {locality.get('level', 'phuong')}",
        f"Trang thông tin: {locality.get('portal', '')}",
        f"Địa chỉ: {contact.get('address', '')}",
        f"Điện thoại: {contact.get('phone', '')}",
        f"Email: {contact.get('email', '')}",
        f"Giờ làm việc ngày thường: {hours.get('weekdays', '')}",
        f"Giờ làm việc thứ Bảy: {hours.get('saturday', '')}",
        f"Chủ nhật: {hours.get('sunday', '')}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest An Phu profile/schedules/procedures")
    parser.add_argument("--skip-procedures", action="store_true")
    parser.add_argument("--limit-procedures", type=int, default=0)
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Re-embed local records even when their document_id already exists",
    )
    args = parser.parse_args()

    setup_logging(settings.log_level)
    chunker = SemanticChunker(settings.chunk_min_size, settings.chunk_max_size)
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()
    existing_ids = set() if args.reingest else load_existing_doc_ids(vector_store)
    log(f"[resume] existing local documents={len(existing_ids)}")
    results: List[Dict[str, Any]] = []

    profile_doc_id = "an_phu_profile"
    profile_text = load_profile_text()
    profile_meta = base_metadata(
        profile_doc_id,
        "Thông tin địa phương",
        "Thông tin liên hệ và giờ làm việc của UBND phường An Phú",
        issued_date="",
        effective_date="",
    )
    if profile_doc_id in existing_ids:
        results.append({"kind": "profile", "documents": 0, "chunks": 0, "skipped": 1})
        log("[profile] skipped")
    else:
        count = ingest_one(
            profile_doc_id,
            profile_text,
            profile_meta,
            chunker,
            embedding_service,
            vector_store,
            replace=args.reingest,
        )
        results.append({"kind": "profile", "documents": 1, "chunks": count, "skipped": 0})
        log(f"[profile] chunks={count}")

    schedules_path = DATA_DIR / "schedules.json"
    if schedules_path.exists():
        schedules = json.loads(schedules_path.read_text(encoding="utf-8"))
        schedule_chunks = 0
        schedule_documents = 0
        schedule_skipped = 0
        for schedule in schedules:
            doc_id = f"an_phu_schedule_{schedule['schedule_id']}"[:120]
            if doc_id in existing_ids:
                schedule_skipped += 1
                continue
            text = f"{schedule['title']}\n\n{schedule['text']}"
            citation = (
                f"Lịch làm việc UBND phường An Phú: {schedule['title']}"
            )
            metadata = base_metadata(
                doc_id,
                "Lịch làm việc",
                citation,
                issued_date=schedule.get("published_at") or "",
                effective_date=schedule.get("published_at") or "",
                source_url=schedule.get("source_url") or "",
                schedule_id=schedule.get("schedule_id") or "",
            )
            schedule_chunks += ingest_one(
                doc_id,
                text,
                metadata,
                chunker,
                embedding_service,
                vector_store,
                replace=args.reingest,
            )
            schedule_documents += 1
        results.append(
            {
                "kind": "schedules",
                "documents": schedule_documents,
                "chunks": schedule_chunks,
                "skipped": schedule_skipped,
            }
        )
        log(
            f"[schedules] new={schedule_documents} skipped={schedule_skipped} "
            f"chunks={schedule_chunks}"
        )

    procedures_path = DATA_DIR / "procedures.jsonl"
    if procedures_path.exists() and not args.skip_procedures:
        rows = [
            json.loads(line)
            for line in procedures_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if args.limit_procedures:
            rows = rows[: args.limit_procedures]
        procedure_chunks = 0
        procedure_documents = 0
        procedure_skipped = 0
        for index, procedure in enumerate(rows, 1):
            doc_id = f"dvc_procedure_{procedure['uuid']}"
            if doc_id in existing_ids:
                procedure_skipped += 1
                continue
            procedure_name = clean_procedure_name(procedure["name"])
            citation = build_procedure_citation(
                procedure["name"], procedure["procedure_id"]
            )
            metadata = base_metadata(
                doc_id,
                "Thủ tục hành chính",
                citation,
                source_url=procedure.get("source_url") or "",
                procedure_id=procedure.get("procedure_id") or "",
                procedure_name=procedure_name,
                procedure_name_norm=normalize_for_match(procedure_name),
                agency=procedure.get("agency") or "",
                applies_to_an_phu=bool(procedure.get("applies_to_an_phu")),
            )
            procedure_chunks += ingest_one(
                doc_id,
                normalize_procedure_text(procedure["text"]),
                metadata,
                chunker,
                embedding_service,
                vector_store,
                replace=args.reingest,
            )
            procedure_documents += 1
            if procedure_documents % 50 == 0 or index == len(rows):
                log(
                    f"[procedures] {index}/{len(rows)} new={procedure_documents} "
                    f"skipped={procedure_skipped} chunks={procedure_chunks}"
                )
        results.append(
            {
                "kind": "procedures",
                "documents": procedure_documents,
                "chunks": procedure_chunks,
                "skipped": procedure_skipped,
            }
        )

    log("Rebuilding BM25S index...")
    index = rebuild_bm25_index(
        vector_store=vector_store,
        persist_dir=settings.bm25s_persist_dir,
        k1=settings.bm25s_k1,
        b=settings.bm25s_b,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "chunks": sum(item["chunks"] for item in results),
        "documents": sum(item["documents"] for item in results),
        "skipped": sum(item.get("skipped", 0) for item in results),
        "collection": vector_store.get_collection_stats(),
        "bm25": index.get_stats() if index else {},
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
