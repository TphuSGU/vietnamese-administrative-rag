"""Parse legal identifiers and years from a user query.

Retrieval must not treat ``15/NQ-HĐND`` as three ordinary tokens: many
documents share ``NQ`` and ``HĐND``. Exact document-number and year constraints
are extracted here and used as metadata boosts/filters by the hybrid retriever.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

DOC_NUMBER_RE = re.compile(
    r"\b\d{1,4}(?:\s*/\s*\d{4})?\s*/\s*"
    r"(?:NQ|TB|QĐ|QD|NĐ|ND|TT|QH)"
    r"(?:\s*[-.]?\s*(?:TTHĐND|TT\.?\s*HĐND|HĐND|HDND|UBND|CP|BTC|BTP|BCA|QH|TAND|VKSND))?\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def normalize_doc_number(value: str) -> str:
    """Accent/punctuation-insensitive key for document numbers."""
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]", "", value)


@dataclass(frozen=True)
class QueryConstraints:
    doc_numbers: Set[str] = field(default_factory=set)
    raw_doc_numbers: List[str] = field(default_factory=list)
    years: Set[str] = field(default_factory=set)

    @property
    def has_doc_number(self) -> bool:
        return bool(self.doc_numbers)

    @property
    def single_year(self) -> str:
        return next(iter(self.years)) if len(self.years) == 1 else ""


def parse_query_constraints(query: str) -> QueryConstraints:
    raw_numbers = [match.group(0).strip() for match in DOC_NUMBER_RE.finditer(query or "")]
    numbers = {normalize_doc_number(number) for number in raw_numbers}
    years = set(YEAR_RE.findall(query or ""))
    return QueryConstraints(
        doc_numbers={number for number in numbers if number},
        raw_doc_numbers=raw_numbers,
        years=years,
    )


def metadata_year(metadata: Dict[str, Any]) -> str:
    for key in ("issued_date", "effective_date"):
        value = str(metadata.get(key) or "")
        if len(value) >= 4 and value[:4].isdigit():
            return value[:4]
    return ""


def doc_number_matches(metadata: Dict[str, Any], constraints: QueryConstraints) -> bool:
    if not constraints.doc_numbers:
        return False
    value = metadata.get("doc_number") or ""
    return normalize_doc_number(str(value)) in constraints.doc_numbers


def year_matches(metadata: Dict[str, Any], constraints: QueryConstraints) -> bool:
    year = metadata_year(metadata)
    return bool(year and year in constraints.years)


def chunk_contains_year(chunk: Any, year: str) -> bool:
    """Budget questions mean the year in the table, not only the issue date."""
    return bool(year and year in (getattr(chunk, "text", "") or ""))


def filter_candidates_by_constraints(
    chunks: Iterable[Any],
    constraints: QueryConstraints,
) -> List[Any]:
    """Prefer exact doc-number/year candidates, fallback to all if none.

    Doc number is a hard preference when present: a user asking for
    ``15/NQ-HĐND`` should not receive a different resolution just because the
    other document has more similar prose. Year is also filtered when the query
    has exactly one year (e.g. "năm 2025"); ranges such as 2025-2030 are left
    untouched.
    """
    items = list(chunks)
    if not items:
        return items

    if constraints.has_doc_number:
        matched = [
            item for item in items
            if doc_number_matches(item.metadata or {}, constraints)
        ]
        if matched:
            items = matched

    if constraints.single_year:
        year = constraints.single_year
        # Prefer chunks whose content names the requested year (budget tables
        # often say "NĂM 2025" even when issued in a different year).
        content_matched = [
            item for item in items
            if chunk_contains_year(item, year)
        ]
        if content_matched:
            items = content_matched
        else:
            matched = [
                item for item in items
                if year_matches(item.metadata or {}, constraints)
            ]
            if matched:
                items = matched

    return items
