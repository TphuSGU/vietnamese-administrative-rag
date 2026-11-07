#!/usr/bin/env python3
"""Fetch An Phu ward legal documents and their PDF attachments.

The ward portal is a Nuxt app. The public list page embeds a devalue-style
payload (``__NUXT_DATA__``) that contains the document metadata *and* the
attachment URLs, unlike the JSON list API which omits attachments.

Usage:
    python scripts/an_phu_fetch.py
    python scripts/an_phu_fetch.py --metadata-only
    python scripts/an_phu_fetch.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from bs4 import BeautifulSoup

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"

PORTAL_BASE = "https://phuonganphu.gov.vn"
LEGAL_LIST_URL = f"{PORTAL_BASE}/van-ban-phap-luat"
USER_AGENT = "Mozilla/5.0 (compatible; AdministrativeAI/0.1; +https://phuonganphu.gov.vn)"

DOC_NUMBER_RE = re.compile(
    r"\b(\d{1,4})\s*(?:/\s*)?(NQ|TB|QĐ|QD|BC|KH|CT|TTr|HD|HĐ|BB|GM|CV)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def log(message: str) -> None:
    print(message, flush=True)


def fetch_bytes(url: str, *, timeout: int = 60, retries: int = 3) -> bytes:
    """Fetch a URL with a small retry/backoff loop."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
                "Referer": PORTAL_BASE,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # network, HTTP, TLS
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"Cannot fetch {url}: {last_error}")


def resolve_nuxt(data: List[Any], index: Any, stack: Optional[Set[int]] = None) -> Any:
    """Resolve one value in Nuxt's flat ``__NUXT_DATA__`` array.

    Container values are indices into ``data``. Primitive values are stored at
    their own index, so once an index resolves to a primitive it is returned.
    """
    if not isinstance(index, int):
        return index
    if index < 0 or index >= len(data):
        return index

    stack = set() if stack is None else stack
    if index in stack:
        return index

    value = data[index]
    next_stack = stack | {index}

    if isinstance(value, int):
        return value
    if isinstance(value, str) or value is None or isinstance(value, (float, bool)):
        return value
    if isinstance(value, list):
        return [resolve_nuxt(data, item, next_stack) for item in value]
    if isinstance(value, dict):
        return {key: resolve_nuxt(data, item, next_stack) for key, item in value.items()}
    return value


def extract_documents(html: str) -> List[Dict[str, Any]]:
    """Extract document objects (with resolved attachments) from a list page."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NUXT_DATA__")
    if script is None or not script.string:
        raise ValueError("__NUXT_DATA__ payload not found")

    data = json.loads(script.string)
    documents: List[Dict[str, Any]] = []

    for index, value in enumerate(data):
        if not isinstance(value, dict):
            continue
        if not {"id", "title", "slug", "attachments"} <= set(value):
            continue

        resolved = resolve_nuxt(data, index)
        if not isinstance(resolved, dict):
            continue
        if not resolved.get("id") or not resolved.get("title"):
            continue
        documents.append(resolved)

    return documents


def fetch_all_documents(max_pages: int = 20) -> List[Dict[str, Any]]:
    """Walk the paginated list page until no new documents appear."""
    by_id: Dict[int, Dict[str, Any]] = {}

    for page in range(1, max_pages + 1):
        url = f"{LEGAL_LIST_URL}?page={page}"
        log(f"[list] page {page}: {url}")
        html = fetch_bytes(url).decode("utf-8", errors="replace")

        page_docs = extract_documents(html)
        new_count = 0
        for document in page_docs:
            doc_id = int(document["id"])
            if doc_id not in by_id:
                by_id[doc_id] = document
                new_count += 1

        log(f"[list] page {page}: {len(page_docs)} documents, {new_count} new")
        if not page_docs or new_count == 0:
            break

    return [by_id[key] for key in sorted(by_id)]


def strip_html(value: str) -> str:
    if not value:
        return ""
    return BeautifulSoup(value, "lxml").get_text(" ", strip=True)


def normalize_issuer(value: str) -> str:
    upper = (value or "").upper()
    if "HỘI ĐỒNG NHÂN DÂN" in upper:
        return "HĐND phường An Phú"
    if "ỦY BAN NHÂN DÂN" in upper:
        return "UBND phường An Phú"
    return value or "UBND phường An Phú"


def display_date(value: Optional[str]) -> str:
    if not value:
        return ""
    match = DATE_RE.match(str(value))
    if not match:
        return str(value)
    year, month, day = match.groups()
    return f"{int(day)}/{int(month)}/{year}"


def parse_doc_number(document: Dict[str, Any], issuer: str) -> str:
    """Best-effort document number from the title/attachment filename.

    The portal often stores the number in the attachment name (e.g.
    ``25 NQ ban hành...pdf``) rather than in the title. We only infer the
    agency suffix when the issuer is unambiguous.
    """
    haystacks = [document.get("title") or ""]
    for attachment in document.get("attachments") or []:
        haystacks.append(attachment.get("name") or "")

    for text in haystacks:
        match = DOC_NUMBER_RE.search(text)
        if not match:
            continue

        number, kind = match.group(1), match.group(2).upper()
        if kind == "NQ":
            suffix = "NQ-HĐND" if "HỘI ĐỒNG" in issuer.upper() else "NQ-UBND"
        elif kind == "TB":
            suffix = "TB-HĐND" if "HỘI ĐỒNG" in issuer.upper() else "TB-UBND"
        elif kind in {"QĐ", "QD"}:
            suffix = "QĐ-UBND"
        elif kind == "BC":
            suffix = "BC-UBND"
        elif kind == "KH":
            suffix = "KH-UBND"
        elif kind == "CT":
            suffix = "CT-UBND"
        else:
            suffix = kind
        return f"{int(number):02d}/{suffix}"

    return ""


def build_citation_label(
    doc_type: str,
    doc_number: str,
    issued_date: str,
    issuer: str,
) -> str:
    date_text = display_date(issued_date)
    if doc_number:
        base = f"{doc_type} số {doc_number}"
    else:
        base = doc_type
    if date_text:
        base += f" ngày {date_text}"
    if issuer:
        base += f" của {issuer}"
    return base.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_pdf(url: str, target: Path, *, force: bool = False) -> Dict[str, Any]:
    """Download one PDF and return its file metadata."""
    if target.exists() and target.stat().st_size > 0 and not force:
        with target.open("rb") as handle:
            is_pdf = handle.read(5) == b"%PDF-"
        if is_pdf:
            return {
                "status": "skipped",
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")

    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/pdf,*/*",
                    "Referer": PORTAL_BASE,
                },
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                content = response.read()

            if not content.startswith(b"%PDF-"):
                raise ValueError("response is not a PDF")

            tmp.write_bytes(content)
            tmp.replace(target)
            return {
                "status": "downloaded",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        except Exception as exc:
            last_error = exc
            tmp.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(2 * attempt)

    return {"status": "failed", "error": str(last_error), "size": 0}


def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w.-]+", "-", name, flags=re.UNICODE).strip("-._")
    return name or "attachment.pdf"


def build_manifest(
    documents: List[Dict[str, Any]],
    data_dir: Path,
    *,
    download: bool,
    force: bool,
    sleep_seconds: float,
) -> Dict[str, Any]:
    pdf_dir = data_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    manifest_docs: List[Dict[str, Any]] = []
    total_pdf = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for index, document in enumerate(documents, 1):
        portal_id = int(document["id"])
        doc_id = f"an_phu_{portal_id}"
        issuer_raw = (document.get("promulgatingAgency") or {}).get("name") or ""
        issuer = normalize_issuer(issuer_raw)
        doc_type = (document.get("field") or {}).get("name") or "Văn bản"
        issued_date = (document.get("published_at") or "")[:10]
        effective_date = (document.get("effective_at") or "")[:10]
        doc_number = parse_doc_number(document, issuer_raw)

        attachments: List[Dict[str, Any]] = []
        pdf_attachments: List[Dict[str, Any]] = []

        for attachment in document.get("attachments") or []:
            url = attachment.get("path") or ""
            kind = (attachment.get("kind") or "").lower()
            is_pdf = kind == "pdf" or url.lower().endswith(".pdf")
            attachment_entry: Dict[str, Any] = {
                "attachment_id": attachment.get("id"),
                "name": attachment.get("name") or "",
                "url": url,
                "kind": kind or ("pdf" if is_pdf else "other"),
                "declared_size": attachment.get("size"),
                "status": "not_downloaded",
                "local_path": "",
                "sha256": "",
                "size": 0,
            }

            if is_pdf:
                total_pdf += 1
                target_name = f"{doc_id}__{attachment.get('id')}.pdf"
                target = pdf_dir / safe_filename(target_name)
                attachment_entry["local_path"] = str(target.relative_to(data_dir))

                if download:
                    log(
                        f"[pdf] {index}/{len(documents)} {doc_id} "
                        f"attachment={attachment.get('id')}"
                    )
                    result = download_pdf(url, target, force=force)
                    attachment_entry.update(result)
                    if result["status"] == "downloaded":
                        downloaded += 1
                    elif result["status"] == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                pdf_attachments.append(attachment_entry)

            attachments.append(attachment_entry)

        primary_pdf = pdf_attachments[0]["local_path"] if pdf_attachments else ""
        citation_label = build_citation_label(
            doc_type=doc_type,
            doc_number=doc_number,
            issued_date=issued_date,
            issuer=issuer,
        )

        manifest_docs.append(
            {
                "doc_id": doc_id,
                "portal_id": portal_id,
                "title": document.get("title") or "",
                "slug": document.get("slug") or "",
                "doc_number": doc_number,
                "doc_type": doc_type,
                "issuer": issuer,
                "issuer_raw": issuer_raw,
                "issued_date": issued_date,
                "effective_date": effective_date,
                "signer": document.get("signer") or "",
                "source_url": f"{LEGAL_LIST_URL}/{document.get('slug') or ''}",
                "summary_text": strip_html(document.get("content") or ""),
                "attachments": attachments,
                "pdf_attachments": pdf_attachments,
                "pdf_count": len(pdf_attachments),
                "pdf_path": primary_pdf,
                "ocr_status": "missing_pdf" if not pdf_attachments else "pending",
                "char_count": 0,
                "citation_label": citation_label,
                "notes": "No PDF attachment on portal" if not pdf_attachments else "",
            }
        )

        if download and pdf_attachments:
            time.sleep(sleep_seconds)

    return {
        "locality": {
            "code": "25975",
            "name": "Phường An Phú",
            "parent": "TP.HCM",
            "portal": PORTAL_BASE,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "list_url": LEGAL_LIST_URL,
            "method": "Nuxt __NUXT_DATA__ payload",
            "document_count": len(manifest_docs),
            "pdf_attachment_count": total_pdf,
        },
        "download_stats": {
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
        },
        "documents": manifest_docs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch An Phu legal documents + PDFs")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only fetch metadata/manifest, do not download PDFs",
    )
    parser.add_argument("--force", action="store_true", help="Re-download existing PDFs")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.4,
        help="Seconds to sleep between PDF downloads (default: 0.4)",
    )
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.data_dir / "raw" / "legal-pages"
    raw_dir.mkdir(parents=True, exist_ok=True)

    documents = fetch_all_documents()
    if len(documents) != 52:
        log(f"[warn] expected 52 documents, got {len(documents)}")

    # Keep the raw page payloads for auditability.
    for page in range(1, 20):
        url = f"{LEGAL_LIST_URL}?page={page}"
        try:
            html = fetch_bytes(url).decode("utf-8", errors="replace")
        except RuntimeError:
            break
        if "__NUXT_DATA__" not in html:
            break
        (raw_dir / f"page-{page}.html").write_text(html, encoding="utf-8")
        if page >= 6:
            break

    manifest = build_manifest(
        documents,
        args.data_dir,
        download=not args.metadata_only,
        force=args.force,
        sleep_seconds=args.sleep,
    )

    manifest_path = args.data_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    stats = manifest["download_stats"]
    log("")
    log("=" * 64)
    log(f"Documents: {len(manifest['documents'])}")
    log(f"PDF attachments: {manifest['source']['pdf_attachment_count']}")
    log(
        "Download: "
        f"{stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, "
        f"{stats['failed']} failed"
    )
    log(f"Manifest: {manifest_path}")
    log("=" * 64)

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
