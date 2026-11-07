#!/usr/bin/env python3
"""Validate manually edited An Phu text files and update the manifest.

The text files live at ``data/localities/an_phu/text/<doc_id>.txt``.  This
script does not touch the text files; it validates them, records the manual
source in the manifest, and refreshes the OCR summary.  The old page-level OCR
audit (``ocr/*.pages.jsonl``) is kept for reference but marked stale.

Usage:
    python scripts/an_phu_import_text.py --dry-run
    python scripts/an_phu_import_text.py
    python scripts/an_phu_import_text.py --only an_phu_2464 an_phu_2796
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"

OCR_ERROR_PATTERNS = {
    "hoi_dong": re.compile(r"HỘI ĐÒNG|HỘI ĐỎNG|HỘI ĐÔNG|HỘI ĐỌNG"),
    "nhan_dan": re.compile(r"NHÂN DẦN|NHÂN ĐÂN|NHAN DAN"),
    "so": re.compile(r"\bSó\b"),
    "replacement": re.compile(r"\ufffd"),
    "html": re.compile(r"<[^>]{1,80}>"),
    "control": re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(message, flush=True)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]", "", value.lower())


def validate_text(text: str, document: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if len(text.strip()) < 200:
        issues.append("too_short")
    if not text.strip():
        issues.append("empty")
    for name, pattern in OCR_ERROR_PATTERNS.items():
        if pattern.search(text):
            issues.append(name)

    head = text[:1500]
    if "Số:" not in head:
        issues.append("no_so")
    if not re.search(r"HỘI ĐỒNG NHÂN DÂN|ỦY BAN NHÂN DÂN|THƯỜNG TRỰC|HĐND|UBND", head, re.I):
        issues.append("no_header")

    doc_number = document.get("doc_number") or ""
    if doc_number and normalize(doc_number) not in normalize(head):
        issues.append("doc_number_mismatch")

    page_count = int(document.get("page_count") or 0)
    if page_count and len(text) / page_count < 200:
        issues.append("low_chars_per_page")
    return issues


def build_summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    documents = manifest.get("documents") or []
    status_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    for document in documents:
        status = document.get("ocr_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        source = document.get("text_source") or "none"
        source_counts[source] = source_counts.get(source, 0) + 1
    return {
        "generated_at": utc_now(),
        "documents": len(documents),
        "text_files": sum(1 for d in documents if d.get("text_path")),
        "pages": sum(int(d.get("page_count") or 0) for d in documents),
        "chars": sum(int(d.get("char_count") or 0) for d in documents),
        "status_counts": status_counts,
        "text_source_counts": source_counts,
        "ocr_audit_stale": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate manual An Phu text files and update manifest"
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="+", default=None)
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        log(f"Manifest không tồn tại: {manifest_path}")
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = set(args.only or [])
    processed = 0
    changed = 0
    warnings: List[Tuple[str, List[str]]] = []

    for document in manifest.get("documents") or []:
        doc_id = document.get("doc_id")
        if selected and doc_id not in selected:
            continue
        text_path = data_dir / (document.get("text_path") or f"text/{doc_id}.txt")
        if not text_path.is_file():
            log(f"[missing] {doc_id}: {text_path}")
            warnings.append((doc_id, ["missing_text_file"]))
            continue

        try:
            text = text_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            log(f"[bad-encoding] {doc_id}: {exc}")
            warnings.append((doc_id, ["bad_encoding"]))
            continue

        issues = validate_text(text, document)
        if issues:
            warnings.append((doc_id, issues))
            log(f"[warn] {doc_id}: {', '.join(issues)}")
        else:
            log(f"[ok] {doc_id}: {len(text)} chars")

        processed += 1
        if args.dry_run:
            continue

        document["text_source"] = "manual"
        document["ocr_status"] = "done"
        document["char_count"] = len(text)
        document["line_count"] = len(text.splitlines())
        document["text_updated_at"] = datetime.fromtimestamp(
            text_path.stat().st_mtime, timezone.utc
        ).isoformat()
        document["pages_audit_stale"] = True
        document["failed_pages"] = 0
        document.pop("quality_flag", None)
        old_notes = document.get("notes") or ""
        if "OCR không đọc được" in old_notes:
            old_notes = ""
        note = "Manual text imported; OCR page audit is stale"
        document["notes"] = f"{old_notes} | {note}" if old_notes else note
        changed += 1

    if args.dry_run:
        log(f"\nDry run: {processed} file(s) checked, no manifest changes.")
        return 0 if not warnings else 1

    summary = build_summary(manifest)
    summary_path = data_dir / "ocr" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log("\n" + "=" * 64)
    log(f"Checked: {processed}, manifest updated: {changed}")
    log(f"Status: {summary['status_counts']}")
    log(f"Sources: {summary['text_source_counts']}")
    log(f"Chars: {summary['chars']:,}")
    log(f"Manifest: {manifest_path}")
    log(f"Summary: {summary_path}")
    log("=" * 64)

    return 0 if not warnings else 1


if __name__ == "__main__":
    sys.exit(main())
