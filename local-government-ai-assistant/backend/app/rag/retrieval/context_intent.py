"""Detect local-context intent so profile/schedule/procedure queries do not
fall back to a similarly-worded legal document."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, FrozenSet, Iterable, List, Optional, Set, Tuple

from app.rag.ingestion.procedure_metadata import normalize_for_match

PROFILE_DOC_TYPE = "Thông tin địa phương"
SCHEDULE_DOC_TYPE = "Lịch làm việc"
PROCEDURE_DOC_TYPE = "Thủ tục hành chính"

PROFILE_TERMS = (
    "gio lam viec",
    "gio mo cua",
    "thoi gian lam viec",
    "thoi gian mo cua",
    "dia chi",
    "dien thoai",
    "so dien thoai",
    "email",
    "lien he",
    "tru so",
    "o dau",
)
PROCEDURE_TERMS = (
    "thu tuc",
    "ho so",
    "giay to",
    "le phi",
    "thoi gian giai quyet",
    "nop ho so",
    "dang ky khai sinh",
    "dang ky thuong tru",
    "dang ky tam tru",
    "dang ky ket hon",
    "thuong tru",
    "cap ban sao",
    "trich luc",
    "chung thuc",
    "xac nhan cu tru",
    "tam tru",
    "tam vang",
)


def _ascii_lower(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", text).strip()


def _token_present(text: str, token: str) -> bool:
    return f" {token} " in f" {text} "


@dataclass(frozen=True)
class ContextIntent:
    kind: str = ""
    doc_type: Optional[str] = None
    periods: FrozenSet[Tuple[int, int]] = field(default_factory=frozenset)

    @property
    def is_profile(self) -> bool:
        return self.kind == "profile"

    @property
    def is_schedule(self) -> bool:
        return self.kind == "schedule"

    @property
    def is_procedure(self) -> bool:
        return self.kind == "procedure"


def parse_schedule_periods(query: str) -> FrozenSet[Tuple[int, int]]:
    """Extract ``tháng 11/2026`` / ``11/2026`` / ``tháng 11 năm 2026``."""
    text = _ascii_lower(query)
    periods: Set[Tuple[int, int]] = set()

    for pattern in (
        r"\bthang\s*(\d{1,2})\s*/\s*(20\d{2})\b",
        r"\bthang\s*(\d{1,2})\s*nam\s*(20\d{2})\b",
        r"\b(\d{1,2})\s*/\s*(20\d{2})\b",
    ):
        for match in re.finditer(pattern, text):
            month, year = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12:
                periods.add((month, year))
    return frozenset(periods)


def parse_context_intent(query: str) -> ContextIntent:
    text = normalize_for_match(query)
    if not text:
        return ContextIntent()

    # "Quy chế tiếp công dân" is a legal document, not a schedule. Require
    # an explicit "lịch" or a time/where question for schedule routing.
    schedule_hint = _token_present(text, "lich") or (
        "tiep cong dan" in text
        and any(
            term in text
            for term in ("ngay", "thang", "tuan", "khi nao", "o dau", "xem")
        )
    )
    if schedule_hint and any(
        term in text
        for term in ("lam viec", "tiep", "hop", "tuan", "thang", "hdnd", "ubnd")
    ):
        return ContextIntent(
            kind="schedule",
            doc_type=SCHEDULE_DOC_TYPE,
            periods=parse_schedule_periods(query),
        )

    if any(term in text for term in PROFILE_TERMS):
        return ContextIntent(kind="profile", doc_type=PROFILE_DOC_TYPE)

    if any(term in text for term in PROCEDURE_TERMS):
        return ContextIntent(kind="procedure", doc_type=PROCEDURE_DOC_TYPE)

    return ContextIntent()


def _schedule_matches_period(chunk: Any, month: int, year: int) -> bool:
    metadata = getattr(chunk, "metadata", {}) or {}
    text = " ".join(
        str(value or "")
        for value in (
            getattr(chunk, "text", ""),
            metadata.get("citation"),
            metadata.get("citation_label"),
            metadata.get("schedule_id"),
        )
    )
    text = _ascii_lower(text)

    for match in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text):
        if int(match.group(2)) == month and int(match.group(3)) == year:
            return True

    for pattern in (
        rf"\bthang\s*{month}\s*/\s*{year}\b",
        rf"\bthang\s*{month}\s*nam\s*{year}\b",
        rf"\b{month}\s*/\s*{year}\b",
    ):
        if re.search(pattern, text):
            return True
    return False


def filter_schedule_candidates(
    chunks: Iterable[Any],
    periods: FrozenSet[Tuple[int, int]],
) -> List[Any]:
    """Return only schedules whose dates mention the requested month/year.

    If the query names a month/year and no schedule matches, the caller should
    return no context instead of the nearest wrong week.
    """
    items = list(chunks)
    if not periods:
        return items
    return [
        chunk
        for chunk in items
        if any(
            _schedule_matches_period(chunk, month, year)
            for month, year in periods
        )
    ]
