"""Normalize DVC procedure names and build safe citations."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


def normalize_for_match(value: str) -> str:
    """Lowercase, remove Vietnamese accents, and collapse punctuation."""
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_procedure_name(name: str) -> str:
    """Remove the DVC prefix so citations never say ``Thủ tục Thủ tục``."""
    value = re.sub(r"\s+", " ", name or "").strip()
    value = re.sub(r"^thủ\s+tục\s+", "", value, flags=re.IGNORECASE)
    return value.strip()


def build_procedure_citation(name: str, procedure_id: str) -> str:
    """Build the user-facing citation without exposing the internal code."""
    base = clean_procedure_name(name) or "hành chính"
    return f"Thủ tục {base}, Cổng DVC quốc gia"


def normalize_procedure_text(text: str) -> str:
    """Remove repeated ``Thủ tục`` in source text without touching other prose."""
    return re.sub(
        r"(?im)^(thủ\s+tục:\s*)thủ\s+tục\s+",
        r"\1",
        text or "",
    )


def procedure_name_from_metadata(metadata: Dict[str, Any]) -> str:
    name = str(metadata.get("procedure_name") or "").strip()
    if name:
        return clean_procedure_name(name)

    citation = str(
        metadata.get("citation") or metadata.get("citation_label") or ""
    ).strip()
    if not citation:
        return ""
    citation = re.sub(r"^thủ\s+tục\s+", "", citation, flags=re.IGNORECASE)
    citation = re.split(r",\s*(?:mã\s+|Cổng DVC quốc gia)", citation, maxsplit=1)[0]
    return clean_procedure_name(citation)


def _tokens(value: str) -> List[str]:
    return [token for token in normalize_for_match(value).split() if token]


def procedure_title_score(query: str, metadata: Dict[str, Any]) -> float:
    """Prefer the exact/short procedure title over a variant.

    Example: query ``đăng ký khai sinh`` should prefer
    ``Đăng ký khai sinh`` over ``Đăng ký khai sinh lưu động``.
    """
    name = procedure_name_from_metadata(metadata)
    if not name:
        return 0.0

    query_norm = normalize_for_match(query)
    name_norm = normalize_for_match(name)
    if not query_norm or not name_norm:
        return 0.0

    score = 0.0
    procedure_id = normalize_for_match(str(metadata.get("procedure_id") or ""))
    if procedure_id:
        compact_query = re.sub(r"[^a-z0-9]", "", query_norm)
        if procedure_id.replace(" ", "") in compact_query:
            score += 2.0

    if f" {name_norm} " in f" {query_norm} ":
        score += 0.5

    query_tokens = set(_tokens(query_norm))
    name_tokens = set(_tokens(name_norm))
    if name_tokens and query_tokens:
        name_coverage = len(query_tokens & name_tokens) / len(name_tokens)
        query_coverage = len(query_tokens & name_tokens) / len(query_tokens)
        # Query coverage prevents long official titles with extra conditions
        # (e.g. "Hỗ trợ người cao tuổi ...") from being lost behind a short
        # but only partially matching procedure.
        score += 0.3 * name_coverage + 0.7 * query_coverage
        score -= min(len(name_tokens), 20) * 0.002

    return score
