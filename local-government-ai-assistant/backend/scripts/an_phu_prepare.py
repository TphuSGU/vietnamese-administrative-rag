#!/usr/bin/env python3
"""Extract text / OCR An Phu PDFs and update the manifest.

The manifest produced by ``an_phu_fetch.py`` is the source of truth.  This
script processes every PDF attachment, writes one text file per document,
writes per-page audit records, and checkpoints the manifest after each document
so a long OCR run can be resumed.

Usage:
    python scripts/an_phu_prepare.py
    python scripts/an_phu_prepare.py --force
    python scripts/an_phu_prepare.py --only an_phu_2784 an_phu_2785
    python scripts/an_phu_prepare.py --limit 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageOps

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"
DEFAULT_TESSERACT = BACKEND_DIR / ".tesseract" / "bin" / "tesseract"
OCR_CONFIG = "--oem 1 --psm 3 -c preserve_interword_spaces=1"
MIN_TEXT_CHARS = 50


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(message, flush=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_tesseract() -> str:
    """Return a usable tesseract executable, preferring the local wrapper."""
    candidates = [
        os.environ.get("TESSERACT_CMD", ""),
        str(DEFAULT_TESSERACT),
        shutil.which("tesseract") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError(
        "Không tìm thấy tesseract. Chạy scripts/setup_tesseract_local.sh "
        "hoặc đặt biến TESSERACT_CMD."
    )


def check_language(tesseract_cmd: str, lang: str) -> None:
    result = subprocess.run(
        [tesseract_cmd, "--list-langs"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if lang not in output.split():
        raise RuntimeError(
            f"Tesseract thiếu language '{lang}'. Có: {output.strip()}"
        )


def is_blank(image: Image.Image, threshold: float = 0.002) -> bool:
    """Heuristic: a page with <0.2% dark pixels is blank/separator."""
    histogram = image.histogram()
    total = sum(histogram) or 1
    return (sum(histogram[:240]) / total) < threshold


def ocr_page(
    page: fitz.Page,
    *,
    dpi: int,
    lang: str,
    timeout: int,
) -> Tuple[str, Optional[str]]:
    """Render one PDF page and OCR it. Return (text, error)."""
    image: Optional[Image.Image] = None
    rgb: Optional[Image.Image] = None
    gray: Optional[Image.Image] = None
    try:
        pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        rgb = Image.frombytes(
            "RGB",
            (pixmap.width, pixmap.height),
            pixmap.samples,
        )
        # Check blankness before contrast/sharpening, otherwise scanner noise
        # and sharpening artefacts look like ink.
        gray = rgb.convert("L")
        if is_blank(gray):
            return "", "blank"
        # Grayscale + contrast + sharpen improves small Vietnamese glyphs
        # without destroying table borders.
        image = ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(
            image,
            lang=lang,
            config=OCR_CONFIG,
            timeout=timeout,
        )
        text = text.strip()
        return text, None if text else "empty OCR result"
    except Exception as exc:  # tesseract timeout / render failure
        return "", str(exc)
    finally:
        if gray is not None:
            gray.close()
        if rgb is not None:
            rgb.close()
        if image is not None:
            image.close()


def process_pdf(
    pdf_path: Path,
    *,
    attachment_id: Any,
    dpi: int,
    lang: str,
    min_chars: int,
    timeout: int,
    progress_prefix: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract text-layer pages and OCR image-only pages."""
    page_records: List[Dict[str, Any]] = []
    page_texts: List[str] = []

    with fitz.open(pdf_path) as pdf:
        total = pdf.page_count
        for page_index in range(total):
            page = pdf[page_index]
            raw_text = page.get_text("text", sort=True).strip()
            method = "text"
            text = raw_text
            error: Optional[str] = None

            if len(raw_text) < min_chars:
                method = "ocr"
                ocr_text, error = ocr_page(
                    page,
                    dpi=dpi,
                    lang=lang,
                    timeout=timeout,
                )
                if error == "blank":
                    method = "blank"
                    text = raw_text
                elif ocr_text:
                    text = ocr_text
                elif raw_text:
                    # Keep whatever text layer exists instead of dropping it.
                    method = "text_fallback"
                    text = raw_text
                else:
                    method = "ocr_failed"

            page_texts.append(text)
            page_records.append(
                {
                    "attachment_id": attachment_id,
                    "pdf_path": str(pdf_path.name),
                    "page": page_index + 1,
                    "method": method,
                    "char_count": len(text),
                    "text_sha256": sha256_text(text) if text else "",
                    "preview": text[:160],
                    "error": error or "",
                }
            )

            if method in {"ocr_failed", "text_fallback"}:
                log(
                    f"{progress_prefix} page {page_index + 1}/{total}: "
                    f"{method.upper()} ({error})"
                )
            elif (page_index + 1) % 5 == 0 or page_index + 1 == total:
                log(
                    f"{progress_prefix} page {page_index + 1}/{total}: "
                    f"{method}, {len(text)} chars"
                )

    combined = "\n\n".join(text for text in page_texts if text.strip())
    return combined, page_records


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def save_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def process_document(
    document: Dict[str, Any],
    *,
    data_dir: Path,
    dpi: int,
    lang: str,
    min_chars: int,
    timeout: int,
    force: bool,
) -> bool:
    """Process one document. Return True when the manifest changed."""
    doc_id = document["doc_id"]
    pdf_attachments = document.get("pdf_attachments") or []
    if not pdf_attachments:
        if document.get("ocr_status") != "missing_pdf":
            document["ocr_status"] = "missing_pdf"
            return True
        return False

    text_path = data_dir / "text" / f"{doc_id}.txt"
    pages_path = data_dir / "ocr" / f"{doc_id}.pages.jsonl"

    if (
        not force
        and document.get("ocr_status") in {"done", "partial"}
        and text_path.is_file()
        and pages_path.is_file()
    ):
        log(f"[skip] {doc_id}: already {document.get('ocr_status')}")
        return False

    all_pages: List[Dict[str, Any]] = []
    all_text: List[str] = []
    attachment_stats: List[Dict[str, Any]] = []

    for index, attachment in enumerate(pdf_attachments, 1):
        local_path = attachment.get("local_path") or ""
        pdf_path = data_dir / local_path
        if not pdf_path.is_file():
            log(f"[error] {doc_id}: missing PDF {pdf_path}")
            attachment_stats.append(
                {
                    "attachment_id": attachment.get("attachment_id"),
                    "status": "missing",
                    "page_count": 0,
                    "char_count": 0,
                }
            )
            continue

        prefix = f"[ocr] {doc_id} {index}/{len(pdf_attachments)}"
        log(f"{prefix}: {pdf_path.name}")
        text, page_records = process_pdf(
            pdf_path,
            attachment_id=attachment.get("attachment_id"),
            dpi=dpi,
            lang=lang,
            min_chars=min_chars,
            timeout=timeout,
            progress_prefix=prefix,
        )
        all_text.append(text)
        all_pages.extend(page_records)

        ocr_count = sum(1 for record in page_records if record["method"] == "ocr")
        text_count = sum(
            1 for record in page_records if record["method"] == "text"
        )
        failed_count = sum(
            1
            for record in page_records
            if record["method"] in {"ocr_failed", "text_fallback"}
        )
        blank_count = sum(
            1 for record in page_records if record["method"] == "blank"
        )
        attachment_stats.append(
            {
                "attachment_id": attachment.get("attachment_id"),
                "status": "done" if failed_count == 0 else "partial",
                "page_count": len(page_records),
                "char_count": len(text),
                "text_pages": text_count,
                "ocr_pages": ocr_count,
                "blank_pages": blank_count,
                "failed_pages": failed_count,
            }
        )

    combined = "\n\n".join(text for text in all_text if text.strip())
    write_text(text_path, combined)
    write_jsonl(pages_path, all_pages)

    failed_pages = sum(
        1
        for record in all_pages
        if record["method"] in {"ocr_failed", "text_fallback"}
    )
    missing_attachments = sum(
        1 for stats in attachment_stats if stats["status"] == "missing"
    )
    text_pages = sum(1 for record in all_pages if record["method"] == "text")
    ocr_pages = sum(1 for record in all_pages if record["method"] == "ocr")
    blank_pages = sum(1 for record in all_pages if record["method"] == "blank")

    if not combined.strip():
        status = "failed"
    elif failed_pages or missing_attachments:
        status = "partial"
    else:
        status = "done"

    document["ocr_status"] = status
    document["page_count"] = len(all_pages)
    document["char_count"] = len(combined)
    document["text_path"] = str(text_path.relative_to(data_dir))
    document["text_pages"] = text_pages
    document["ocr_pages"] = ocr_pages
    document["blank_pages"] = blank_pages
    document["failed_pages"] = failed_pages
    document["missing_attachments"] = missing_attachments
    document["processed_at"] = utc_now()
    document["attachment_ocr"] = attachment_stats

    if failed_pages:
        document["quality_flag"] = "ocr_failed_pages"
    elif combined and len(combined) < 200:
        document["quality_flag"] = "short_text"
    else:
        document.pop("quality_flag", None)

    for attachment, stats in zip(pdf_attachments, attachment_stats):
        attachment.update(stats)

    log(
        f"[done] {doc_id}: {status}, {len(all_pages)} pages, "
        f"{len(combined)} chars, text={text_pages}, ocr={ocr_pages}, "
        f"failed={failed_pages}"
    )
    return True


def build_summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    documents = manifest.get("documents") or []
    status_counts: Dict[str, int] = {}
    for document in documents:
        status = document.get("ocr_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "generated_at": utc_now(),
        "documents": len(documents),
        "pages": sum(int(document.get("page_count") or 0) for document in documents),
        "chars": sum(int(document.get("char_count") or 0) for document in documents),
        "text_pages": sum(int(document.get("text_pages") or 0) for document in documents),
        "ocr_pages": sum(int(document.get("ocr_pages") or 0) for document in documents),
        "blank_pages": sum(
            int(document.get("blank_pages") or 0) for document in documents
        ),
        "failed_pages": sum(
            int(document.get("failed_pages") or 0) for document in documents
        ),
        "missing_attachments": sum(
            int(document.get("missing_attachments") or 0) for document in documents
        ),
        "status_counts": status_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract text / OCR An Phu PDFs and update manifest"
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--force", action="store_true", help="Re-process all documents")
    parser.add_argument("--only", nargs="+", default=None, help="Only these doc_ids")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N docs")
    parser.add_argument("--dpi", type=int, default=400)
    parser.add_argument("--min-chars", type=int, default=MIN_TEXT_CHARS)
    parser.add_argument("--timeout", type=int, default=180, help="OCR timeout/page")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        log(f"Manifest không tồn tại: {manifest_path}")
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest.get("documents") or []
    if not documents:
        log("Manifest không có documents.")
        return 2

    tesseract_cmd = resolve_tesseract()
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    check_language(tesseract_cmd, "vie")
    log(f"Tesseract: {tesseract_cmd}")
    log(f"Data dir: {data_dir}")

    selected = set(args.only or [])
    processed = 0
    changed = 0
    started = time.perf_counter()

    for index, document in enumerate(documents, 1):
        doc_id = document.get("doc_id")
        if selected and doc_id not in selected:
            continue
        if args.limit and processed >= args.limit:
            break

        log(f"\n[{index}/{len(documents)}] {doc_id}")
        processed += 1
        if process_document(
            document,
            data_dir=data_dir,
            dpi=args.dpi,
            lang="vie",
            min_chars=args.min_chars,
            timeout=args.timeout,
            force=args.force,
        ):
            changed += 1
            save_manifest(manifest_path, manifest)

    manifest["ocr"] = {
        "engine": "tesseract",
        "lang": "vie",
        "dpi": args.dpi,
        "min_chars": args.min_chars,
        "config": OCR_CONFIG,
        "updated_at": utc_now(),
    }
    summary = build_summary(manifest)
    summary["dpi"] = args.dpi
    summary["last_run_elapsed_seconds"] = round(time.perf_counter() - started, 1)
    summary_path = data_dir / "ocr" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_manifest(manifest_path, manifest)

    log("\n" + "=" * 64)
    log(f"Processed: {processed}, changed: {changed}")
    log(f"Pages: {summary['pages']}, chars: {summary['chars']}")
    log(
        f"Text pages: {summary['text_pages']}, "
        f"OCR pages: {summary['ocr_pages']}, "
        f"failed: {summary['failed_pages']}"
    )
    log(f"Status: {summary['status_counts']}")
    log(f"Manifest: {manifest_path}")
    log(f"Summary: {summary_path}")
    log("=" * 64)

    return 0 if summary["status_counts"].get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
