"""Tests for legal citation validation in generated answers."""

from app.models.data_models import RetrievedChunk
from app.rag.generation.output_validator import OutputValidator


TEXT = (
    "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú "
    "quy định mục tiêu, nhiệm vụ và giải pháp bảo đảm an sinh xã hội "
    "giai đoạn 2025-2030 trên địa bàn phường."
)


def make_chunk(**metadata):
    base = {
        "doc_number": "24/NQ-HĐND",
        "citation_label": "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú",
        "citation": "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú, Điều 1",
    }
    base.update(metadata)
    return RetrievedChunk(text=TEXT, similarity_score=0.9, metadata=base)


def test_answer_with_legal_citation_passes():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Theo Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú, "
        "Điều 1, nghị quyết quy định mục tiêu, nhiệm vụ và giải pháp bảo đảm "
        "an sinh xã hội giai đoạn 2025-2030 trên địa bàn phường."
    )
    valid, error = validator.validate(answer, "an sinh xã hội", [make_chunk()])
    assert valid is True, error


def test_answer_without_legal_citation_fails():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Nghị quyết quy định mục tiêu, nhiệm vụ và giải pháp bảo đảm "
        "an sinh xã hội giai đoạn 2025-2030 trên địa bàn phường."
    )
    valid, error = validator.validate(answer, "an sinh xã hội", [make_chunk()])
    assert valid is False
    assert "Missing legal citation" in error


def test_answer_with_internal_id_fails():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Theo Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú, "
        "Điều 1, document_id an_phu_2837 quy định mục tiêu an sinh xã hội."
    )
    valid, error = validator.validate(answer, "an sinh xã hội", [make_chunk()])
    assert valid is False
    assert "internal reference" in error


def test_chunks_without_citation_skip_citation_check():
    validator = OutputValidator(min_evidence_ratio=0.0)
    chunk = RetrievedChunk(
        text=TEXT,
        similarity_score=0.9,
        metadata={"document_id": "old-doc"},
    )
    answer = (
        "Nghị quyết quy định mục tiêu, nhiệm vụ và giải pháp bảo đảm "
        "an sinh xã hội giai đoạn 2025-2030 trên địa bàn phường."
    )
    valid, error = validator.validate(answer, "an sinh xã hội", [chunk])
    assert valid is True, error


def test_honest_refusal_skips_citation_requirement():
    """Câu 'không tìm thấy thông tin' là câu trả lời đúng khi corpus không có."""
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Tôi không tìm thấy thông tin đầy đủ trong các tài liệu được cung cấp "
        "về việc tỉnh An Phú được sáp nhập với tỉnh nào."
    )
    valid, error = validator.validate(answer, "tỉnh an phú sáp nhập", [make_chunk()])
    assert valid is True, error


def test_refusal_still_blocks_internal_reference():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Tôi không tìm thấy thông tin trong tài liệu. "
        "Tài liệu document_id an_phu_2837 không liên quan."
    )
    valid, error = validator.validate(answer, "sáp nhập", [make_chunk()])
    assert valid is False
    assert "internal reference" in error


def test_validate_direct_skips_evidence_and_citation():
    """Câu trả lời không có context thì bỏ qua evidence + citation."""
    validator = OutputValidator(min_evidence_ratio=0.99)
    answer = (
        "Hiện chưa có thông tin chính thức trong tài liệu của địa phương về việc "
        "sáp nhập tỉnh An Phú, bạn nên liên hệ UBND phường để được hướng dẫn."
    )
    valid, error = validator.validate_direct(answer, "tỉnh an phú sáp nhập")
    assert valid is True, error


def test_validate_direct_still_rejects_internal_reference():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = "Tra cứu tại document_id an_phu_2837 để biết thêm thông tin chi tiết."
    valid, error = validator.validate_direct(answer, "tra cứu")
    assert valid is False
    assert "Internal reference" in error


def test_schedule_tail_citation_after_colon_passes():
    """Câu trả lời trích đuôi label sau dấu ':' (mô hình hay làm vậy) vẫn đạt."""
    validator = OutputValidator(min_evidence_ratio=0.0)
    chunk = make_chunk(
        doc_number=None,
        citation_label=(
            "Lịch làm việc UBND phường An Phú: Lịch làm việc HĐND - UBND "
            "ngày 12/01/2026 đến 17/01/2026"
        ),
        citation=(
            "Lịch làm việc UBND phường An Phú: Lịch làm việc HĐND - UBND "
            "ngày 12/01/2026 đến 17/01/2026"
        ),
    )
    answer = (
        "Thứ Hai 12/01/2026 Chủ tịch UBND giải quyết công việc tại cơ quan "
        "(Lịch làm việc HĐND - UBND ngày 12/01/2026 đến 17/01/2026)."
    )
    valid, error = validator.validate(answer, "lịch làm việc", [chunk])
    assert valid is True, error


def test_short_colon_tail_does_not_weaken_citation_check():
    """Đuôi quá ngắn sau ':' không được coi là citation hợp lệ."""
    validator = OutputValidator(min_evidence_ratio=0.0)
    chunk = make_chunk(doc_number=None, citation_label="Nguồn: UBND", citation="")
    answer = "UBND giải quyết công việc theo quy định hiện hành."
    valid, error = validator.validate(answer, "ubnd", [chunk])
    assert valid is False
    assert "Missing legal citation" in error


def test_answer_with_url_fails():
    """Phase 8: câu trả lời không được chứa URL (citation chỉ số hiệu/ngày)."""
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú quy "
        "định an sinh xã hội, chi tiết tại https://example.gov.vn/nq-24."
    )
    valid, error = validator.validate(answer, "an sinh xã hội", [make_chunk()])
    assert valid is False
    assert "URL" in error


def test_refusal_with_url_fails():
    """Câu từ chối cũng không được chứa URL."""
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Tôi không tìm thấy thông tin đầy đủ trong tài liệu, tham khảo "
        "https://example.gov.vn để biết thêm."
    )
    valid, error = validator.validate(answer, "sáp nhập", [make_chunk()])
    assert valid is False
    assert "URL" in error


def test_direct_answer_with_url_fails():
    validator = OutputValidator(min_evidence_ratio=0.0)
    answer = (
        "Hiện chưa có thông tin chính thức trong tài liệu của địa phương về "
        "việc sáp nhập, xem chi tiết tại https://example.gov.vn."
    )
    valid, error = validator.validate_direct(answer, "sáp nhập")
    assert valid is False
    assert "URL" in error
