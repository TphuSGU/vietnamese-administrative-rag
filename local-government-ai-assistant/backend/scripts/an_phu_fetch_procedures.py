#!/usr/bin/env python3
"""Fetch/resume DVC commune procedures and normalize to procedures.jsonl."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"
RAW_DIR = DATA_DIR / "raw" / "procedures"
LIST_URL = "https://dichvucong.gov.vn/api/v1/submitting/formality/list-all-public-formality-by-citizen"
DETAIL_URL = "https://dichvucong.gov.vn/api/v1/configuring/formality/get-formality-by-citizen"
HEADERS = [
    "-H", "Content-Type: application/json; charset=UTF-8",
    "-H", "Accept: application/json, text/plain, */*",
    "-H", "Origin: https://dichvucong.gov.vn",
    "-H", "Referer: https://dichvucong.gov.vn/",
    "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def log(message: str) -> None:
    print(message, flush=True)


def post_json(url: str, body: Dict[str, Any], retries: int = 5) -> Dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False)
    last_error = ""
    for attempt in range(1, retries + 1):
        command = ["curl", "-sS", "-m", "30", "-X", "POST", url, *HEADERS, "--data", payload]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if data.get("code") == "OK":
                    return data
                last_error = f"API code {data.get('code')}: {data.get('message')}"
            except json.JSONDecodeError:
                last_error = result.stdout[:200]
        else:
            last_error = result.stderr.strip() or "empty response"
        if attempt < retries:
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Cannot POST {url}: {last_error}")


def fetch_list(limit: int, page_size: int = 200) -> List[Dict[str, Any]]:
    items: Dict[str, Dict[str, Any]] = {}
    last_id = ""
    while True:
        log(f"[list] fetched={len(items)} lastId={last_id or '-'}")
        data = post_json(
            LIST_URL,
            {"level": "COMMUNE", "limit": page_size, "lastId": last_id, "q": ""},
        )["data"]
        page_items = data.get("items") or []
        new = 0
        for item in page_items:
            item_id = item.get("id")
            if item_id and item_id not in items:
                items[item_id] = item
                new += 1
        next_id = data.get("lastId") or ""
        if limit and len(items) >= limit:
            break
        if not page_items or not next_id or next_id == last_id or new == 0:
            break
        last_id = next_id
        time.sleep(1.0)
    return list(items.values())


def normalize(detail: Dict[str, Any], list_item: Dict[str, Any]) -> Dict[str, Any]:
    code = str(detail.get("codeNotation") or detail.get("code") or list_item.get("code") or "")
    uuid = str(detail.get("id") or list_item.get("id") or "")
    name = str(detail.get("name") or list_item.get("name") or "")

    required_docs: List[str] = []
    for case in detail.get("executionCases") or []:
        for component in case.get("profileComponents") or []:
            value = str(component.get("name") or "").strip()
            if value and value not in required_docs:
                required_docs.append(value)

    processing_time = ""
    for method in detail.get("executionMethods") or []:
        qty = method.get("processingTime")
        unit = method.get("processingTimeUnit") or ""
        if qty:
            processing_time = f"{qty} {unit}".strip()
            break
    if not processing_time:
        for case in detail.get("cases") or []:
            day = case.get("processingDay") or {}
            if day.get("qty"):
                processing_time = f"{day.get('qty')} {day.get('type') or ''}".strip()
                break

    fees: List[str] = []
    for method in detail.get("executionMethods") or []:
        for fee in method.get("fees") or []:
            value = fee.get("value")
            if value is not None:
                text = f"{value} {fee.get('currencyId') or 'VNĐ'}".strip()
                if text not in fees:
                    fees.append(text)
    fee = "; ".join(fees)

    legal_basis = [
        str(item.get("name") or "").strip()
        for item in detail.get("legalBasisesDetails") or []
        if item.get("name")
    ]
    agency = "UBND phường An Phú"
    unit_groups = [
        group for group in (detail.get("unitGroupsExecuting") or [])
        if isinstance(group, dict)
    ]
    if unit_groups:
        agency = str(unit_groups[0].get("name") or agency)
    applies = bool(detail.get("isWard") or unit_groups)

    search_text = "\n".join(
        part for part in [
            f"Thủ tục: {name}",
            f"Mã thủ tục: {code}",
            f"Cơ quan thực hiện: {agency}",
            f"Mô tả: {detail.get('description') or ''}",
            "Hồ sơ: " + "; ".join(required_docs),
            f"Thời gian giải quyết: {processing_time}",
            f"Lệ phí: {fee}",
            "Căn cứ pháp lý: " + "; ".join(legal_basis),
        ] if part and not part.endswith(": ")
    )

    return {
        "procedure_id": code,
        "uuid": uuid,
        "name": name,
        "level": "COMMUNE",
        "locality_code": "25975",
        "locality_scope": "commune",
        "applies_to_an_phu": applies,
        "agency": agency,
        "description": str(detail.get("description") or ""),
        "required_documents": required_docs,
        "processing_time": processing_time,
        "fee": fee,
        "legal_basis": legal_basis,
        "source_url": f"https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-nganh-doc.html?ma_thu_tuc={code}",
        "raw_json_path": f"raw/procedures/{uuid}.json",
        "text": search_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch DVC commune procedures")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-details", action="store_true")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    items = fetch_list(args.limit)
    log(f"[list] total items: {len(items)}")
    details: List[Dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        uuid = str(item.get("id") or "")
        raw_path = RAW_DIR / f"{uuid}.json"
        if raw_path.exists():
            detail = json.loads(raw_path.read_text(encoding="utf-8"))
        elif args.skip_details:
            detail = dict(item)
        else:
            log(f"[detail] {index}/{len(items)} {item.get('code')} {str(item.get('name'))[:60]}")
            detail = post_json(DETAIL_URL, {"id": uuid})["data"]
            raw_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(1.0)
        details.append(normalize(detail, item))

    output = DATA_DIR / "procedures.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in details:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    log(f"[procedures] wrote {len(details)} rows to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
