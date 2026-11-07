"""Phase 10: citation_label builder — có/không số hiệu, có/không ngày."""

from app.rag.ingestion.citation import (
    build_chunk_citation,
    build_document_citation,
    citation_from_metadata,
)


def test_full_document_citation():
    label = build_document_citation(
        doc_type="Nghị quyết",
        doc_number="24/NQ-HĐND",
        issued_date="2026-07-31",
        issuer="HĐND phường An Phú",
    )
    assert label == (
        "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú"
    )
    assert "http" not in label


def test_citation_without_doc_number():
    label = build_document_citation(
        doc_type="Lịch làm việc",
        doc_number="",
        issued_date="2026-01-12",
        issuer="UBND phường An Phú",
    )
    assert "số" not in label
    assert label.startswith("Lịch làm việc")
    assert "ngày 12/1/2026" in label


def test_citation_without_date():
    label = build_document_citation(
        doc_type="Thông báo",
        doc_number="12/TB-UBND",
        issued_date="",
        issuer="UBND phường An Phú",
    )
    assert "ngày" not in label
    assert label == "Thông báo số 12/TB-UBND của UBND phường An Phú"


def test_citation_without_number_and_date():
    label = build_document_citation(
        doc_type="", doc_number="", issued_date="", issuer=""
    )
    assert label == "Văn bản"


def test_chunk_citation_appends_structure_units():
    label = build_chunk_citation(
        {
            "citation_label": "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026",
            "article_no": "1",
            "clause_no": "2",
            "point_no": "a",
        }
    )
    assert label.endswith(", Điều 1, khoản 2, điểm a")


def test_chunk_citation_prefers_citation_label():
    label = build_chunk_citation(
        {
            "citation_label": "Lịch làm việc UBND phường An Phú: Lịch làm việc",
            "doc_type": "Khác",
            "doc_number": "99/KH",
        }
    )
    assert label.startswith("Lịch làm việc UBND phường An Phú")


def test_citation_from_metadata_handles_empty():
    assert citation_from_metadata(None) == ""
    assert citation_from_metadata({}) == ""


def test_chunk_citation_never_contains_url():
    label = build_chunk_citation(
        {
            "citation_label": "Nghị quyết số 24/NQ-HĐND",
            "source_url": "https://example.gov.vn/nq-24",
        }
    )
    assert "http" not in label
