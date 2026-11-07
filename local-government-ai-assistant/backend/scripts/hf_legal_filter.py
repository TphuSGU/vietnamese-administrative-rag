#!/usr/bin/env python3
"""Filter the Vietnamese legal HF snapshot and build hf_manifest.json.

This stage does not embed anything. It selects current HCMC + priority central
documents, joins their HTML content, cleans it to text, and writes:

    data/legal_hf/hf_manifest.json
    data/legal_hf/hf_documents.jsonl

Usage:
    python scripts/hf_legal_filter.py --dry-run
    python scripts/hf_legal_filter.py --max-docs 10000
    python scripts/hf_legal_filter.py --max-docs 500 --out data/legal_hf/pilot
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pyarrow.parquet as pq
from bs4 import BeautifulSoup

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BACKEND_DIR / "data" / "legal_hf" / "raw" / "data"
DEFAULT_OUT = BACKEND_DIR / "data" / "legal_hf"

METADATA_COLUMNS = [
    "id", "title", "so_ky_hieu", "ngay_ban_hanh", "loai_van_ban",
    "ngay_co_hieu_luc", "ngay_het_hieu_luc", "co_quan_ban_hanh",
    "pham_vi", "linh_vuc", "nganh", "tinh_trang_hieu_luc",
]
PRIORITY_PATTERN = re.compile(
    "ho tich|cu tru|can cuoc|chung minh nhan dan|dat dai|nha o|xay dung|"
    "khieu nai|to cao|tiep cong dan|ngan sach|dau tu cong|lao dong|"
    "bao tro xa hoi|an sinh xa hoi|y te|giao duc|hon nhan|gia dinh|"
    "doanh nghiep|ho kinh doanh|thu tuc hanh chinh|chinh quyen dia phuong|"
    "to chuc bien che|cong chuc|vien chuc"
)
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def log(message: str) -> None:
    print(message, flush=True)


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact_code(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize(value))


def iso_date(value: Any) -> str:
    match = DATE_RE.match(str(value or "").strip())
    if not match:
        return ""
    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def sort_date(value: Any) -> Tuple[int, int, int]:
    iso = iso_date(value)
    if not iso:
        return (0, 0, 0)
    year, month, day = iso.split("-")
    return (int(year), int(month), int(day))


def clean_html(raw: str, title: str) -> str:
    soup = BeautifulSoup(raw or "", "lxml")
    for node in soup(["script", "style", "meta", "link"]):
        node.decompose()
    text = soup.get_text("\n")
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    body = "\n".join(lines)
    body = re.sub(r"\n{2,}", "\n\n", body).strip()
    title = re.sub(r"\s+", " ", title or "").strip()
    if title and normalize(title) not in normalize(body[:800]):
        body = f"{title}\n\n{body}"
    return body


def build_citation(row: Dict[str, Any]) -> str:
    doc_type = str(row.get("loai_van_ban") or "Văn bản").strip()
    number = str(row.get("so_ky_hieu") or "").strip()
    issued = str(row.get("ngay_ban_hanh") or "").strip()
    issuer = str(row.get("co_quan_ban_hanh") or "").strip()
    label = f"{doc_type} số {number}" if number else doc_type
    if issued:
        label = f"{label} ngày {issued}"
    if issuer:
        label = f"{label} của {issuer}"
    return label


def interleave(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    index = 0
    while index < len(left) or index < len(right):
        if index < len(left):
            output.append(left[index])
        if index < len(right):
            output.append(right[index])
        index += 1
    return output


def select_candidates(metadata: List[Dict[str, Any]], limit: int) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    hcm: List[Dict[str, Any]] = []
    central: List[Dict[str, Any]] = []
    current = 0
    for row in metadata:
        if row.get("tinh_trang_hieu_luc") != "Còn hiệu lực":
            continue
        current += 1
        issuer = normalize(row.get("co_quan_ban_hanh"))
        scope = normalize(row.get("pham_vi"))
        field = normalize(
            " ".join(str(row.get(key) or "") for key in ("linh_vuc", "nganh", "title"))
        )
        is_hcm = "ho chi minh" in issuer or "hcm" in issuer or "ho chi minh" in scope
        is_central = scope in {"trung uong", "toan quoc"} and bool(
            PRIORITY_PATTERN.search(field)
        )
        if is_hcm:
            hcm.append(row)
        elif is_central:
            central.append(row)

    hcm.sort(key=lambda row: sort_date(row.get("ngay_ban_hanh")), reverse=True)
    central.sort(key=lambda row: sort_date(row.get("ngay_ban_hanh")), reverse=True)

    # Deduplicate by so_ky_hieu, keeping the newest row. HCMC wins ties.
    seen: set[str] = set()
    hcm_dedup: List[Dict[str, Any]] = []
    central_dedup: List[Dict[str, Any]] = []
    for group, target in ((hcm, hcm_dedup), (central, central_dedup)):
        for row in group:
            code = compact_code(row.get("so_ky_hieu")) or f"id:{row.get('id')}"
            if code in seen:
                continue
            seen.add(code)
            target.append(row)

    # Interleave so a small pilot tests both HCMC and central, while the full
    # selection still puts all 2,152 HCMC documents in.
    candidates = interleave(hcm_dedup, central_dedup)
    selected = candidates[: max(limit + 500, limit)] if limit else candidates
    return selected, {
        "current_total": current,
        "hcm_current": len(hcm),
        "central_priority_current": len(central),
        "hcm_dedup": len(hcm_dedup),
        "central_dedup": len(central_dedup),
    }


def iter_selected_content(content_path: Path, wanted: set[str]) -> Iterable[Dict[str, Any]]:
    parquet = pq.ParquetFile(content_path)
    for batch in parquet.iter_batches(batch_size=4000, columns=["id", "content_html"]):
        for row in batch.to_pylist():
            if row.get("id") in wanted:
                yield row


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter HF legal snapshot")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-docs", type=int, default=10000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    metadata_path = args.input_dir / "metadata.parquet"
    content_path = args.input_dir / "content.parquet"
    if not metadata_path.exists() or not content_path.exists():
        raise SystemExit(f"Missing HF parquet in {args.input_dir}")

    table = pq.read_table(metadata_path, columns=METADATA_COLUMNS)
    rows = table.to_pylist()
    candidates, counts = select_candidates(rows, args.max_docs)
    log(
        f"[filter] metadata={len(rows)} current={counts['current_total']} "
        f"hcm={counts['hcm_current']} central={counts['central_priority_current']} "
        f"dedup={counts['hcm_dedup'] + counts['central_dedup']} "
        f"candidates={len(candidates)}"
    )
    if args.dry_run:
        log(f"[dry-run] would select up to {args.max_docs} documents")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    wanted_ids = {str(row["id"]) for row in candidates}
    content: Dict[str, str] = {}
    for index, row in enumerate(iter_selected_content(content_path, wanted_ids), 1):
        content[str(row["id"])] = row.get("content_html") or ""
        if index % 1000 == 0:
            log(f"[content] matched={len(content)}")

    documents: List[Dict[str, Any]] = []
    missing_content = 0
    for row in candidates:
        raw = content.get(str(row["id"]))
        if not raw:
            missing_content += 1
            continue
        text = clean_html(raw, str(row.get("title") or ""))
        if not text:
            missing_content += 1
            continue
        row = dict(row)
        doc_id = f"hf_{row['id']}"
        row.update(
            {
                "doc_id": doc_id,
                "doc_scope": "hcmc" if normalize(row.get("co_quan_ban_hanh")).find("ho chi minh") >= 0 or normalize(row.get("pham_vi")).find("ho chi minh") >= 0 else "central",
                "issued_date": iso_date(row.get("ngay_ban_hanh")),
                "effective_date": iso_date(row.get("ngay_co_hieu_luc")),
                "citation_label": build_citation(row),
                "text": text,
            }
        )
        documents.append(row)
        if len(documents) >= args.max_docs:
            break

    selected_hcm = sum(1 for row in documents if row["doc_scope"] == "hcmc")
    selected_central = len(documents) - selected_hcm
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "th1nhng0/vietnamese-legal-documents",
        "snapshot": "2026-07-23",
        "filters": {
            "status": "Còn hiệu lực",
            "scope": "HCMC + central priority fields",
            "dedup": "so_ky_hieu, newest first",
            "cap": args.max_docs,
        },
        "counts": {
            **counts,
            "selected": len(documents),
            "selected_hcmc": selected_hcm,
            "selected_central": selected_central,
            "missing_or_empty_content": missing_content,
        },
        "documents": [
            {key: value for key, value in row.items() if key != "text"}
            for row in documents
        ],
    }
    (args.out / "hf_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.out / "hf_documents.jsonl").open("w", encoding="utf-8") as handle:
        for row in documents:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    log(
        f"[done] selected={len(documents)} hcmc={selected_hcm} "
        f"central={selected_central} missing_content={missing_content}"
    )
    log(f"[out] {args.out / 'hf_manifest.json'}")
    log(f"[out] {args.out / 'hf_documents.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
