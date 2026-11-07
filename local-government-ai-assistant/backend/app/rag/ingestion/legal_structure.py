"""Vietnamese legal structure detection for chunk-level citations.

The chunker keeps text and heading context, but a chunk needs explicit
``Điều`` / ``khoản`` / ``điểm`` numbers so citations do not depend on the LLM
guessing from prose. This module only detects line-start headings; references
inside a sentence ("theo Điều 5") are intentionally ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from app.models.data_models import Chunk

# Manual text from some converters keeps Markdown bold markers (**Điều 1.**).
# Allow them without leaking ** into citation titles.
ARTICLE_RE = re.compile(
    r"^\s*\*{0,2}Điều\s+(\d+[a-zA-Z]?)\s*[.:]\s*\*{0,2}\s*(.*?)\s*\*{0,2}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CLAUSE_RE = re.compile(
    r"^\s*\*{0,2}(?:Khoản\s+)?(\d{1,3})\s*[.)]\s*\*{0,2}\s+(.+?)\s*\*{0,2}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# Lowercase only: uppercase Roman numerals (I, II, V) are budget table rows,
# not legal points. Vietnamese points are a, b, c, d, đ...
POINT_RE = re.compile(
    r"^\s*\*{0,2}(?:(?:Điểm|điểm)\s+)?([a-zđ])\s*[.)]\s*\*{0,2}\s+(.+?)\s*\*{0,2}\s*$",
    re.MULTILINE,
)
# Annex headings are not part of the last Điều. Budget tables and lists often
# sit after "Điều 3. Hiệu lực thi hành"; without this reset they would be
# cited as "Điều 3", which is legally wrong.
ANNEX_RE = re.compile(
    r"^\s*\*{0,2}((?:PHỤ LỤC|DANH SÁCH|DANH MỤC|BIỂU|BẢNG|MẪU)"
    r"(?:\s+[^\n]{0,160})?)\s*\*{0,2}\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class LegalUnit:
    kind: str  # article | clause | point | annex
    number: str
    title: str
    start: int
    end: int


def _iter_units(text: str, regex: re.Pattern[str], kind: str) -> Iterable[LegalUnit]:
    for match in regex.finditer(text):
        if regex.groups >= 2:
            number = match.group(1).strip()
            title = (match.group(2) or "").strip()
        else:
            number = ""
            title = (match.group(1) or "").strip()
        yield LegalUnit(
            kind=kind,
            number=number,
            title=title,
            start=match.start(),
            end=match.end(),
        )


def extract_units(text: str) -> List[LegalUnit]:
    """Return legal units ordered by position in the document."""
    units = (
        list(_iter_units(text, ARTICLE_RE, "article"))
        + list(_iter_units(text, CLAUSE_RE, "clause"))
        + list(_iter_units(text, POINT_RE, "point"))
        + list(_iter_units(text, ANNEX_RE, "annex"))
    )
    units.sort(key=lambda unit: unit.start)
    return units


def _match_in_chunk(chunk: Chunk, regex: re.Pattern[str]) -> Optional[re.Match[str]]:
    return regex.search(chunk.text)


def annotate_chunks(chunks: List[Chunk], text: str) -> None:
    """Attach article/clause/point metadata to chunks in place.

    A chunk can span multiple units; the first unit in the chunk is the most
    useful citation anchor, falling back to the latest unit before the chunk.
    """
    units = extract_units(text)
    unit_index = 0
    current_article: Optional[LegalUnit] = None
    current_clause: Optional[LegalUnit] = None
    current_point: Optional[LegalUnit] = None
    current_annex: Optional[LegalUnit] = None

    for chunk in chunks:
        start = max(0, chunk.char_start or 0)
        while unit_index < len(units) and units[unit_index].start <= start:
            unit = units[unit_index]
            if unit.kind == "annex":
                current_annex = unit
                current_article = None
                current_clause = None
                current_point = None
            elif unit.kind == "article":
                current_article = unit
                current_clause = None
                current_point = None
            elif unit.kind == "clause":
                current_clause = unit
                current_point = None
            else:
                current_point = unit
            unit_index += 1

        article_match = _match_in_chunk(chunk, ARTICLE_RE)
        clause_match = _match_in_chunk(chunk, CLAUSE_RE)
        point_match = _match_in_chunk(chunk, POINT_RE)
        annex_match = _match_in_chunk(chunk, ANNEX_RE)

        if annex_match:
            # A chunk that contains an annex heading must not inherit the
            # previous article (usually "Điều 3. Hiệu lực thi hành").
            article_no = ""
            clause_no = ""
            point_no = ""
            annex_title = annex_match.group(1).strip()
        else:
            article_no = article_match.group(1) if article_match else (
                current_article.number if current_article else ""
            )
            clause_no = clause_match.group(1) if clause_match else (
                current_clause.number if current_clause else ""
            )
            point_no = point_match.group(1) if point_match else (
                current_point.number if current_point else ""
            )
            annex_title = current_annex.title if current_annex else ""

        annex_title = re.sub(r"\s+", " ", annex_title).strip()
        legal_heading = (
            (annex_title if annex_title else "")
            or (article_match.group(2).strip() if article_match else "")
            or (current_article.title if current_article else "")
        )

        chunk.metadata.update(
            {
                "article_no": article_no.lower(),
                "clause_no": str(clause_no),
                "point_no": str(point_no).lower(),
                "annex_title": annex_title[:250],
                "legal_heading": legal_heading[:250],
            }
        )


def structure_stats(text: str) -> Dict[str, int]:
    """Small helper for QA/reporting."""
    units = extract_units(text)
    return {
        "articles": sum(1 for unit in units if unit.kind == "article"),
        "clauses": sum(1 for unit in units if unit.kind == "clause"),
        "points": sum(1 for unit in units if unit.kind == "point"),
        "annexes": sum(1 for unit in units if unit.kind == "annex"),
    }
