"""Build human-facing citations from trusted metadata.

Never include URLs here: the UI citation contract is document number, date,
issuer, and (when present) article/clause/point. The LLM is instructed to use
these strings instead of inventing source numbers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

ANNEX_LABELS = (
    ("DANH SÁCH", "Danh sách"),
    ("DANH MỤC", "Danh mục"),
    ("PHỤ LỤC", "Phụ lục"),
    ("BIỂU SỐ", "Biểu số"),
    ("BIỂU MẪU", "Biểu mẫu"),
    ("MẪU SỐ", "Mẫu số"),
    ("BIỂU", "Biểu"),
    ("BẢNG", "Bảng"),
    ("MẪU", "Mẫu"),
)


def _format_annex(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title:
        return "Phụ lục"
    upper = title.upper()
    for prefix, label in ANNEX_LABELS:
        if upper.startswith(prefix):
            return f"{label}{title[len(prefix):]}"
    return f"Phụ lục {title}"


def _format_date(iso_date: str) -> str:
    try:
        year, month, day = iso_date.split("-")
        return f"{int(day)}/{int(month)}/{year}"
    except (AttributeError, ValueError):
        return iso_date or ""


def build_document_citation(
    doc_type: str,
    doc_number: str,
    issued_date: str,
    issuer: str,
) -> str:
    """Build a document-level citation without a URL."""
    parts = [part for part in (doc_type, doc_number) if part]
    label = " số ".join(parts) if parts else "Văn bản"
    date = _format_date(issued_date)
    if date:
        label = f"{label} ngày {date}"
    if issuer:
        label = f"{label} của {issuer}"
    return label.strip()


def build_chunk_citation(metadata: Dict[str, Any]) -> str:
    """Append Điều/khoản/điểm to the document citation when available."""
    base = (metadata.get("citation_label") or "").strip()
    if not base:
        base = build_document_citation(
            str(metadata.get("doc_type") or ""),
            str(metadata.get("doc_number") or ""),
            str(metadata.get("issued_date") or ""),
            str(metadata.get("issuer") or ""),
        )

    units = []
    annex_title = str(metadata.get("annex_title") or "").strip()
    article_no = str(metadata.get("article_no") or "").strip()
    clause_no = str(metadata.get("clause_no") or "").strip()
    point_no = str(metadata.get("point_no") or "").strip()
    if annex_title:
        units.append(_format_annex(annex_title))
    if article_no:
        units.append(f"Điều {article_no}")
    if clause_no:
        units.append(f"khoản {clause_no}")
    if point_no:
        units.append(f"điểm {point_no}")

    if units:
        return f"{base}, {', '.join(units)}"
    return base


def citation_from_metadata(
    metadata: Optional[Dict[str, Any]],
) -> str:
    """Safe helper for callers that may pass empty/None metadata."""
    if not metadata:
        return ""
    return build_chunk_citation(metadata)
