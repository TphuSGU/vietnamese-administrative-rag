#!/usr/bin/env python3
"""Fetch An Phu profile and work-schedule pages.

The portal exposes schedules as article pages with a PDF attachment. This
script collects the 18 links, downloads the PDFs, extracts text, and writes
``schedules.json`` + ``profile.yaml`` next to the legal manifest.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz
from bs4 import BeautifulSoup

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data" / "localities" / "an_phu"
PORTAL_BASE = "https://phuonganphu.gov.vn"
USER_AGENT = "Mozilla/5.0 (compatible; AdministrativeAI/0.1)"
DATE_RE = re.compile(r"ngày\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)
PDF_RE = re.compile(r"https?://[^\"']+\.pdf", re.IGNORECASE)


def log(message: str) -> None:
    print(message, flush=True)


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,*/*",
            "Referer": PORTAL_BASE,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def discover_schedule_links(max_pages: int = 6) -> List[str]:
    links: List[str] = []
    for page in range(1, max_pages + 1):
        url = f"{PORTAL_BASE}/lich-lam-viec?page={page}"
        html = fetch_bytes(url).decode("utf-8", errors="replace")
        page_links = re.findall(r'href="(/lich-lam-viec/[^"]+)"', html)
        new = 0
        for link in page_links:
            if link not in links:
                links.append(link)
                new += 1
        log(f"[schedules] page {page}: {len(page_links)} links, {new} new")
        if new == 0:
            break
    return links


def extract_pdf_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = "\n\n".join(page.get_text("text", sort=True).strip() for page in doc)
    if len(text.strip()) >= 50:
        return text.strip()

    # Scan fallback with the local tesseract wrapper.
    tesseract = BACKEND_DIR / ".tesseract" / "bin" / "tesseract"
    if not tesseract.exists():
        tesseract = Path(shutil.which("tesseract") or "")
    if not tesseract.exists():
        return text.strip()

    import pytesseract
    from PIL import Image, ImageOps, ImageFilter

    pytesseract.pytesseract.tesseract_cmd = str(tesseract)
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=300, colorspace=fitz.csRGB, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        image = ImageOps.autocontrast(image).filter(ImageFilter.SHARPEN)
        pages.append(
            pytesseract.image_to_string(image, lang="vie", config="--psm 6", timeout=90)
        )
    return "\n\n".join(page.strip() for page in pages if page.strip())


def fetch_schedules() -> List[Dict[str, Any]]:
    links = discover_schedule_links()
    raw_dir = DATA_DIR / "raw" / "schedules"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for index, link in enumerate(links, 1):
        url = PORTAL_BASE + link
        log(f"[schedules] {index}/{len(links)} {link}")
        html = fetch_bytes(url).decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        title = (soup.title.string or "").strip()
        date_match = DATE_RE.search(title)
        published = (
            f"{date_match.group(3)}-{int(date_match.group(2)):02d}-{int(date_match.group(1)):02d}"
            if date_match
            else ""
        )
        pdf_match = PDF_RE.search(html)
        if not pdf_match:
            log("  [warn] no PDF attachment")
            continue
        pdf_url = pdf_match.group(0)
        slug = link.rsplit("/", 1)[-1]
        pdf_path = raw_dir / f"{slug}.pdf"
        if not pdf_path.exists():
            pdf_path.write_bytes(fetch_bytes(pdf_url))
        text = extract_pdf_text(pdf_path)
        results.append(
            {
                "schedule_id": slug,
                "title": title,
                "published_at": published,
                "source_url": url,
                "pdf_url": pdf_url,
                "pdf_path": str(pdf_path.relative_to(DATA_DIR)),
                "text": text,
                "locality_code": "25975",
                "locality_name": "Phường An Phú",
            }
        )
    return results


def write_profile() -> None:
    profile = """locality:
  code: "25975"
  name: "Phường An Phú"
  level: "phuong"
  parent: "Thành phố Hồ Chí Minh"
  portal: "https://phuonganphu.gov.vn"

contact:
  address: "Số 9, đường ĐT 743, khu phố 1A, Thành phố Hồ Chí Minh"
  phone: "02743 740021"
  email: "anphu@tphcm.gov.vn"

working_hours:
  weekdays: "07:30-11:30, 13:30-17:00"
  saturday: "07:30-11:30"
  sunday: "Nghỉ"
"""
    path = DATA_DIR / "profile.yaml"
    path.write_text(profile, encoding="utf-8")
    log(f"[profile] wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch An Phu profile/schedules")
    parser.add_argument("--skip-schedules", action="store_true")
    args = parser.parse_args()

    write_profile()
    if not args.skip_schedules:
        schedules = fetch_schedules()
        path = DATA_DIR / "schedules.json"
        path.write_text(
            json.dumps(schedules, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"[schedules] wrote {len(schedules)} items to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
