"""Tests for local-context routing and procedure title ranking."""

from app.models.data_models import RetrievedChunk
from app.rag.ingestion.procedure_metadata import (
    build_procedure_citation,
    procedure_title_score,
)
from app.rag.retrieval.context_intent import (
    filter_schedule_candidates,
    parse_context_intent,
    parse_schedule_periods,
)
from app.rag.retrieval.hybrid_retriever import HybridRetriever


def test_working_hours_routes_to_profile():
    intent = parse_context_intent("Giờ làm việc của phường An Phú?")
    assert intent.is_profile
    assert intent.doc_type == "Thông tin địa phương"


def test_working_time_routes_to_profile():
    intent = parse_context_intent("Cho tôi biết thời gian làm việc của phường An Phú")
    assert intent.is_profile


def test_schedule_intent_extracts_month_and_year():
    intent = parse_context_intent("Lịch tiếp công dân tháng 11/2026?")
    assert intent.is_schedule
    assert intent.periods == frozenset({(11, 2026)})


def test_quy_che_tiep_cong_dan_is_not_a_schedule():
    intent = parse_context_intent("Quy chế tiếp công dân của phường quy định gì?")
    assert not intent.is_schedule
    assert intent.doc_type is None


def test_procedure_intent_for_birth_registration():
    intent = parse_context_intent("Thủ tục đăng ký khai sinh cần giấy tờ gì?")
    assert intent.is_procedure
    assert intent.doc_type == "Thủ tục hành chính"


def test_procedure_intent_for_permanent_residence():
    intent = parse_context_intent("Đăng ký thường trú mất bao lâu?")
    assert intent.is_procedure
    assert intent.doc_type == "Thủ tục hành chính"


def test_schedule_period_parser_accepts_vietnamese_and_slash_forms():
    assert parse_schedule_periods("lịch tháng 11 năm 2026") == frozenset({(11, 2026)})
    assert parse_schedule_periods("lịch 01/2026") == frozenset({(1, 2026)})


def test_schedule_period_filter_rejects_wrong_month():
    chunks = [
        RetrievedChunk(
            text="Lịch làm việc ngày 12/01/2026 đến 17/01/2026",
            similarity_score=1.0,
            metadata={"document_id": "jan"},
        ),
        RetrievedChunk(
            text="Lịch làm việc ngày 17/11/2026 đến 21/11/2026",
            similarity_score=0.9,
            metadata={"document_id": "nov"},
        ),
    ]
    filtered = filter_schedule_candidates(chunks, frozenset({(11, 2026)}))
    assert [chunk.metadata["document_id"] for chunk in filtered] == ["nov"]


def test_schedule_period_filter_returns_empty_when_none_match():
    chunks = [
        RetrievedChunk(
            text="Lịch làm việc ngày 12/01/2026",
            similarity_score=1.0,
            metadata={"document_id": "jan"},
        )
    ]
    assert filter_schedule_candidates(chunks, frozenset({(11, 2026)})) == []


def test_short_exact_procedure_title_beats_variant():
    query = "Thủ tục đăng ký khai sinh cần giấy tờ gì?"
    exact = {"procedure_name": "Đăng ký khai sinh"}
    variant = {"procedure_name": "Đăng ký khai sinh lưu động"}
    assert procedure_title_score(query, exact) > procedure_title_score(query, variant)


def test_long_procedure_title_still_beats_generic_support_title():
    query = "Hỗ trợ người cao tuổi từ 70 đến dưới 75 tuổi cần hồ sơ gì?"
    long_title = {
        "procedure_name": (
            "Hỗ trợ cho Người cao tuổi từ đủ 70 tuổi đến dưới 75 tuổi; "
            "Người cao tuổi dưới 75 tuổi thường trú trên địa bàn tỉnh, "
            "là Đảng viên được tặng huy hiệu 40 năm tuổi đảng trở lên, "
            "không có lương hưu, trợ cấp bảo hiểm xã hội"
        )
    }
    generic = {"procedure_name": "Hỗ trợ sinh kế, tự học nghề"}
    assert procedure_title_score(query, long_title) > procedure_title_score(
        query, generic
    )


def test_procedure_citation_does_not_repeat_prefix():
    citation = build_procedure_citation("Thủ tục đăng ký khai sinh", "1.001193")
    assert "Thủ tục Thủ tục" not in citation
    assert citation == "Thủ tục đăng ký khai sinh, Cổng DVC quốc gia"


def test_dedupe_keeps_higher_scored_duplicate():
    chunks = [
        RetrievedChunk("same", 0.01, {"document_id": "a", "chunk_index": 13}),
        RetrievedChunk("same", 0.60, {"document_id": "a", "chunk_index": 13}),
    ]
    deduped = HybridRetriever._dedupe(chunks)
    assert len(deduped) == 1
    assert deduped[0].similarity_score == 0.60


def test_limit_per_document_keeps_context_diverse():
    chunks = [
        RetrievedChunk("a1", 1.0, {"document_id": "a"}),
        RetrievedChunk("a2", 0.9, {"document_id": "a"}),
        RetrievedChunk("a3", 0.8, {"document_id": "a"}),
        RetrievedChunk("b1", 0.7, {"document_id": "b"}),
    ]
    limited = HybridRetriever._limit_per_document(chunks, max_per_document=2)
    assert [chunk.metadata["document_id"] for chunk in limited] == ["a", "a", "b"]
