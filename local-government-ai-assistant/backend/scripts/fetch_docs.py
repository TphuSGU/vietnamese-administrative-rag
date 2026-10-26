#!/usr/bin/env python3
"""
Download official Công Báo documents for the RAG test corpus.

The signed PDFs published on vanban.chinhphu.vn are usually scans, while the
Công Báo versions of the same documents have a real text layer. This script
downloads the Công Báo PDFs, optionally merges multi-part documents, and
verifies that a usable text layer exists before ingestion.

Usage:
    python scripts/fetch_docs.py
    python scripts/fetch_docs.py --force
    python scripts/fetch_docs.py --manifest data/sources.json --out data/raw
"""

import argparse
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = BACKEND_DIR / "data" / "sources.json"
DEFAULT_OUT_DIR = BACKEND_DIR / "data" / "raw"

USER_AGENT = "Mozilla/5.0 (compatible; AdministrativeAI/0.1; +https://chinhphu.vn)"
MIN_CHARS_PER_PAGE = 500


def download(url: str, target: Path, force: bool = False) -> None:
    """Download a URL to target with retries (idempotent unless force)."""
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"    skip (exists): {target.name}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target.with_suffix(target.suffix + ".part")

    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(tmp_target, "wb") as handle:
                    shutil.copyfileobj(response, handle)
            tmp_target.replace(target)
            size_kb = target.stat().st_size / 1024
            print(f"    downloaded: {target.name} ({size_kb:.0f} KB)")
            return
        except Exception as exc:  # network/SSL/HTTP errors
            last_error = exc
            print(f"    attempt {attempt}/3 failed: {exc}")
            time.sleep(2 * attempt)

    raise RuntimeError(f"Cannot download {url}: {last_error}")


def merge_pdf(parts: List[Path], target: Path) -> None:
    """Merge PDF parts into a single PDF using PyMuPDF."""
    merged = fitz.open()
    try:
        for part in parts:
            with fitz.open(part) as source:
                merged.insert_pdf(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.save(target)
    finally:
        merged.close()


def inspect_pdf(path: Path) -> Dict:
    """Return page count and text statistics for a PDF."""
    with fitz.open(path) as pdf:
        pages = pdf.page_count
        text = "\n".join(page.get_text() for page in pdf)

    chars = len(text)
    return {
        "file": path.name,
        "pages": pages,
        "chars": chars,
        "chars_per_page": round(chars / pages, 1) if pages else 0,
        "text_layer_ok": pages > 0 and (chars / pages) >= MIN_CHARS_PER_PAGE,
    }


def process_document(entry: Dict, out_dir: Path, force: bool) -> Dict:
    doc_id = entry["doc_id"]
    urls = entry.get("urls") or []
    if not urls:
        raise ValueError(f"{doc_id}: manifest entry has no urls")

    include_parts = entry.get("include_parts")
    if include_parts is not None:
        urls = [urls[index] for index in include_parts if 0 <= index < len(urls)]

    target = out_dir / f"{doc_id}.pdf"
    parts_dir = out_dir / ".parts"
    part_paths = [parts_dir / f"{doc_id}-part-{index}.pdf" for index in range(len(urls))]

    print(f"\n[{doc_id}] {len(urls)} part(s)")

    if target.exists() and not force:
        print(f"    target exists, verifying: {target.name}")
    else:
        for url, part_path in zip(urls, part_paths):
            download(url, part_path, force=force)

        if len(part_paths) == 1:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(part_paths[0], target)
        else:
            merge_pdf(part_paths, target)
            print(f"    merged {len(part_paths)} parts -> {target.name}")

        for part_path in part_paths:
            part_path.unlink(missing_ok=True)

    stats = inspect_pdf(target)
    stats["doc_id"] = doc_id
    stats["doc_number"] = entry.get("doc_number")
    stats["title"] = entry.get("title")
    stats["effective_date"] = entry.get("effective_date")
    stats["source_type"] = entry.get("source_type", "congbao")
    stats["source_urls"] = urls

    if stats["text_layer_ok"]:
        print(
            f"    OK: {stats['pages']} pages, {stats['chars']} chars "
            f"({stats['chars_per_page']} chars/page)"
        )
    else:
        print(
            f"    WARNING: weak text layer ({stats['chars_per_page']} chars/page). "
            "This document likely needs OCR before ingestion."
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Công Báo PDFs for RAG")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    resolved = []
    for entry in manifest:
        resolved.append(process_document(entry, args.out, args.force))

    report_path = args.out / "manifest.resolved.json"
    report_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print(f"{'doc_id':<20} {'pages':>6} {'chars':>9} {'chars/page':>11} {'ok':>4}")
    print("-" * 70)
    for stats in resolved:
        print(
            f"{stats['doc_id']:<20} {stats['pages']:>6} {stats['chars']:>9} "
            f"{stats['chars_per_page']:>11} {str(stats['text_layer_ok']):>4}"
        )
    print("=" * 70)
    print(f"Report: {report_path}")

    return 0 if all(item["text_layer_ok"] for item in resolved) else 1


if __name__ == "__main__":
    sys.exit(main())
