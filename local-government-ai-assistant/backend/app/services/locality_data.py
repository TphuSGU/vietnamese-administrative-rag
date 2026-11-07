"""File-backed readers for locality reference data (Phase 9 demo).

Demo decision (2026-11-07): profile/schedules/procedures/manifest stay as
files under ``data/localities/<slug>/`` and are read directly with a
process-level cache — the PostgreSQL tables of plan §4.6 are deferred until
there is a real persistence need. Every payload is field-whitelisted so
source_url/pdf_url/portal never reach the API.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCALITIES_DIR = BACKEND_DIR / "data" / "localities"

# slug (URL) -> locality_code used by retrieval/API defaults
KNOWN_LOCALITIES = {"an-phu": "25975"}

# Process-level cache: files are static for a running demo; tests can clear it.
_cache: Dict[str, Any] = {}


def reset_cache() -> None:
    """Drop cached files (used by tests that touch data on disk)."""
    _cache.clear()


def _locality_dir(slug: str) -> Path:
    return LOCALITIES_DIR / slug.replace("-", "_")


def _cached(key: str, loader):
    if key not in _cache:
        _cache[key] = loader()
    return _cache[key]


def _load_yaml(slug: str) -> dict:
    def loader() -> dict:
        path = _locality_dir(slug) / "profile.yaml"
        if not path.exists():
            raise FileNotFoundError(str(path))
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    return _cached(f"profile:{slug}", loader)


def _load_schedules(slug: str) -> list:
    def loader() -> list:
        path = _locality_dir(slug) / "schedules.json"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as fh:
            return json.load(fh) or []

    return _cached(f"schedules:{slug}", loader)


def _load_manifest(slug: str) -> list:
    def loader() -> list:
        path = _locality_dir(slug) / "manifest.json"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as fh:
            manifest = json.load(fh) or {}
        documents = manifest.get("documents")
        if isinstance(documents, dict):
            documents = list(documents.values())
        return documents or []

    return _cached(f"manifest:{slug}", loader)


def _load_procedures(slug: str) -> list:
    def loader() -> list:
        path = _locality_dir(slug) / "procedures.jsonl"
        if not path.exists():
            return []
        rows: List[dict] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    return _cached(f"procedures:{slug}", loader)


def _norm(text: Optional[str]) -> str:
    """Lowercase + strip Vietnamese accents so 'ho tich' matches 'hộ tịch'."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


def _slug_for_code(locality_code: str) -> Optional[str]:
    for slug, code in KNOWN_LOCALITIES.items():
        if code == locality_code:
            return slug
    return None


def get_profile(slug: str = "an-phu") -> dict:
    """Profile payload for the chat UI: locality, contact, hours, 18 schedules."""
    data = _load_yaml(slug)
    schedules = [
        {
            "schedule_id": row.get("schedule_id") or "",
            "title": row.get("title") or "",
            "published_at": row.get("published_at") or "",
        }
        for row in _load_schedules(slug)
    ]
    verification = data.get("verification") or None
    return {
        "locality": {
            "code": str((data.get("locality") or {}).get("code") or ""),
            "name": (data.get("locality") or {}).get("name") or "",
            "level": (data.get("locality") or {}).get("level") or "",
            "parent": (data.get("locality") or {}).get("parent") or "",
        },
        "contact": data.get("contact") or {},
        "working_hours": data.get("working_hours") or {},
        "schedules": schedules,
        "verification": verification,
    }


def list_procedures(
    locality_code: str,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """Filter procedures by locality + accent-insensitive free text."""
    slug = _slug_for_code(locality_code)
    if slug is None:
        return [], 0
    rows = _load_procedures(slug)
    needle = _norm(q)
    matched: List[dict] = []
    for row in rows:
        if str(row.get("locality_code") or "") != locality_code:
            continue
        if needle:
            haystack = " ".join(
                _norm(row.get(field))
                for field in ("name", "description", "agency")
            )
            if needle not in haystack:
                continue
        matched.append(
            {
                "procedure_id": row.get("procedure_id") or "",
                "name": row.get("name") or "",
                "agency": row.get("agency") or "",
                "level": row.get("level") or "",
                "locality_code": row.get("locality_code") or "",
                "description": (row.get("description") or "")[:500],
                "required_documents": row.get("required_documents") or [],
                "processing_time": row.get("processing_time") or "",
                "fee": row.get("fee") or "",
                "legal_basis": row.get("legal_basis") or [],
            }
        )
    return matched[offset : offset + limit], len(matched)


def list_legal_documents(
    locality_code: str,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """Filter manifest documents by locality + free text (title/số hiệu/cơ quan)."""
    slug = _slug_for_code(locality_code)
    if slug is None:
        return [], 0
    needle = _norm(q)
    matched: List[dict] = []
    for row in _load_manifest(slug):
        if needle:
            haystack = " ".join(
                _norm(row.get(field))
                for field in ("title", "doc_number", "issuer", "doc_type")
            )
            if needle not in haystack:
                continue
        matched.append(
            {
                "doc_id": row.get("doc_id") or "",
                "title": row.get("title") or "",
                "doc_number": row.get("doc_number") or "",
                "doc_type": row.get("doc_type") or "",
                "issuer": row.get("issuer") or "",
                "issued_date": row.get("issued_date") or "",
                "effective_date": row.get("effective_date") or "",
                "ocr_status": row.get("ocr_status") or "",
                "doc_scope": "local",
                "citation_label": row.get("citation_label") or "",
            }
        )
    return matched[offset : offset + limit], len(matched)
