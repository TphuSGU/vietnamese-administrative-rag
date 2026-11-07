"""Tests for legal structure detection and citation building."""

from app.models.data_models import Chunk
from app.rag.ingestion.citation import build_chunk_citation, build_document_citation
from app.rag.ingestion.legal_structure import annotate_chunks, extract_units, structure_stats


SAMPLE = """Điều 1. Phạm vi điều chỉnh
1. Quy định này áp dụng cho cơ quan nhà nước.
a) Cơ quan trung ương;
b) Cơ quan địa phương.
Điều 2. Đối tượng áp dụng
1. Cán bộ, công chức.
"""


def test_extract_units_counts_articles_clauses_points():
    stats = structure_stats(SAMPLE)
    assert stats == {"articles": 2, "clauses": 2, "points": 2, "annexes": 0}
    units = extract_units(SAMPLE)
    assert [unit.number for unit in units if unit.kind == "article"] == ["1", "2"]


def test_annotate_chunks_attaches_nearest_structure():
    chunks = [
        Chunk(
            text="Điều 1. Phạm vi điều chỉnh\n1. Quy định này áp dụng cho cơ quan nhà nước.",
            document_id="doc",
            chunk_index=0,
            char_start=0,
            char_end=80,
        ),
        Chunk(
            text="a) Cơ quan trung ương;",
            document_id="doc",
            chunk_index=1,
            char_start=SAMPLE.index("a) Cơ quan"),
            char_end=SAMPLE.index("a) Cơ quan") + 20,
        ),
        Chunk(
            text="Điều 2. Đối tượng áp dụng\n1. Cán bộ, công chức.",
            document_id="doc",
            chunk_index=2,
            char_start=SAMPLE.index("Điều 2"),
            char_end=len(SAMPLE),
        ),
    ]

    annotate_chunks(chunks, SAMPLE)

    assert chunks[0].metadata["article_no"] == "1"
    assert chunks[0].metadata["clause_no"] == "1"
    assert chunks[1].metadata["article_no"] == "1"
    assert chunks[1].metadata["point_no"] == "a"
    assert chunks[2].metadata["article_no"] == "2"
    assert chunks[2].metadata["clause_no"] == "1"


def test_build_chunk_citation_includes_article_clause_point():
    citation = build_chunk_citation(
        {
            "citation_label": "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025 của HĐND phường An Phú",
            "article_no": "5",
            "clause_no": "2",
            "point_no": "a",
        }
    )
    assert citation == (
        "Nghị quyết số 01/NQ-HĐND ngày 1/7/2025 của HĐND phường An Phú, "
        "Điều 5, khoản 2, điểm a"
    )
    assert "http" not in citation


def test_build_document_citation_formats_date():
    citation = build_document_citation(
        "Nghị quyết",
        "05/NQ-HĐND",
        "2026-03-30",
        "HĐND phường An Phú",
    )
    assert citation == "Nghị quyết số 05/NQ-HĐND ngày 30/3/2026 của HĐND phường An Phú"


def test_annex_resets_article_and_cites_annex():
    text = (
        "Điều 1. Nội dung\n"
        "1. Quy định chung.\n"
        "Điều 2. Hiệu lực thi hành\n"
        "PHỤ LỤC I\n"
        "Bảng số liệu ngân sách\n"
        "1 | Tổng thu | 100\n"
    )
    annex_start = text.index("PHỤ LỤC I")
    chunks = [
        Chunk(
            text="Điều 2. Hiệu lực thi hành",
            document_id="doc",
            chunk_index=0,
            char_start=text.index("Điều 2"),
            char_end=annex_start,
        ),
        Chunk(
            text="PHỤ LỤC I\nBảng số liệu ngân sách\n1 | Tổng thu | 100",
            document_id="doc",
            chunk_index=1,
            char_start=annex_start,
            char_end=len(text),
        ),
    ]

    annotate_chunks(chunks, text)

    assert chunks[0].metadata["article_no"] == "2"
    assert chunks[1].metadata["article_no"] == ""
    assert chunks[1].metadata["annex_title"].startswith("PHỤ LỤC")
    citation = build_chunk_citation(
        {
            "citation_label": "Nghị quyết số 15/NQ-HĐND ngày 29/7/2025",
            **chunks[1].metadata,
        }
    )
    assert "Phụ lục" in citation
    assert "Điều 2" not in citation
