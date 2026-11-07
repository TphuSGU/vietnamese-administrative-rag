"""Tests for legal query constraint extraction and filtering."""

from app.models.data_models import RetrievedChunk
from app.rag.retrieval.query_constraints import (
    filter_candidates_by_constraints,
    normalize_doc_number,
    parse_query_constraints,
)


def test_normalize_doc_number_ignores_case_accents_and_spacing():
    assert normalize_doc_number("15 / NQ-HĐND") == normalize_doc_number("15/NQ-HDND")


def test_parse_exact_document_number_and_year():
    constraints = parse_query_constraints("Nghị quyết 15/NQ-HĐND năm 2025 quy định gì?")
    assert normalize_doc_number("15/NQ-HĐND") in constraints.doc_numbers
    assert constraints.single_year == "2025"


def test_filter_prefers_exact_document_number():
    chunks = [
        RetrievedChunk(
            text="wrong number",
            similarity_score=1.0,
            metadata={"doc_number": "24/NQ-HĐND", "issued_date": "2026-07-31"},
        ),
        RetrievedChunk(
            text="right number",
            similarity_score=0.5,
            metadata={"doc_number": "15/NQ-HĐND", "issued_date": "2025-07-29"},
        ),
    ]
    constraints = parse_query_constraints("15/NQ-HĐND")
    filtered = filter_candidates_by_constraints(chunks, constraints)
    assert [chunk.metadata["doc_number"] for chunk in filtered] == ["15/NQ-HĐND"]


def test_filter_prefers_single_query_year():
    chunks = [
        RetrievedChunk(
            text="2026",
            similarity_score=1.0,
            metadata={"doc_number": "02/NQ-HĐND", "issued_date": "2026-01-09"},
        ),
        RetrievedChunk(
            text="2025",
            similarity_score=0.5,
            metadata={"doc_number": "15/NQ-HĐND", "issued_date": "2025-07-29"},
        ),
    ]
    constraints = parse_query_constraints("dự toán ngân sách năm 2025")
    filtered = filter_candidates_by_constraints(chunks, constraints)
    assert [chunk.metadata["issued_date"] for chunk in filtered] == ["2025-07-29"]


def test_filter_prefers_year_in_content_over_issue_date():
    chunks = [
        RetrievedChunk(
            text="Dự toán ngân sách phường năm 2026",
            similarity_score=1.0,
            metadata={"doc_number": "22/NQ-HĐND", "issued_date": "2025-12-24"},
        ),
        RetrievedChunk(
            text="Dự toán ngân sách phường năm 2025",
            similarity_score=0.5,
            metadata={"doc_number": "15/NQ-HĐND", "issued_date": "2025-07-29"},
        ),
    ]
    constraints = parse_query_constraints("dự toán ngân sách phường năm 2025")
    filtered = filter_candidates_by_constraints(chunks, constraints)
    assert [chunk.metadata["doc_number"] for chunk in filtered] == ["15/NQ-HĐND"]


def test_multi_year_range_does_not_hard_filter_year():
    chunks = [
        RetrievedChunk(
            text="2026",
            similarity_score=1.0,
            metadata={"doc_number": "02/NQ-HĐND", "issued_date": "2026-01-09"},
        ),
        RetrievedChunk(
            text="2030",
            similarity_score=0.5,
            metadata={"doc_number": "24/NQ-HĐND", "issued_date": "2030-01-01"},
        ),
    ]
    constraints = parse_query_constraints("an sinh xã hội giai đoạn 2025-2030")
    filtered = filter_candidates_by_constraints(chunks, constraints)
    assert len(filtered) == 2
