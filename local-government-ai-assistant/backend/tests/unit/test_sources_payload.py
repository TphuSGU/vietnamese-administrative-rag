"""sources_payload keeps citation fields for chat history (Phase 8)."""

from app.services.conversations import sources_payload


def test_payload_includes_citation_fields():
    chunks = [
        {
            "document_id": "an_phu_2788",
            "chunk_index": 3,
            "similarity_score": 0.91,
            "text": "Điều 3. Quyền và nghĩa vụ của công dân",
            "citation": "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026, Điều 3",
            "doc_number": "25/NQ-HĐND",
            "issued_date": "2026-07-29",
            "issuer": "HĐND phường An Phú",
            "doc_scope": "local",
            "doc_type": "Nghị quyết",
        }
    ]

    payload = sources_payload(chunks)

    assert len(payload) == 1
    assert payload[0]["citation"].startswith("Nghị quyết số 25")
    assert payload[0]["doc_number"] == "25/NQ-HĐND"
    assert payload[0]["issued_date"] == "2026-07-29"
    assert payload[0]["issuer"] == "HĐND phường An Phú"
    assert payload[0]["doc_scope"] == "local"
    assert payload[0]["doc_type"] == "Nghị quyết"


def test_payload_defaults_missing_citation_to_empty_string():
    """Old chunks without citation metadata still serialise safely."""
    payload = sources_payload(
        [{"document_id": "doc_1", "chunk_index": 0, "similarity_score": 0.5, "text": "x"}]
    )

    assert payload[0]["citation"] == ""
    assert payload[0]["doc_number"] == ""
    assert payload[0]["issued_date"] == ""
    assert payload[0]["issuer"] == ""
    assert payload[0]["doc_scope"] == ""
    assert payload[0]["doc_type"] == ""


def test_payload_strips_urls_from_text():
    """profile.yaml portal URL must never reach chat history (plan §8.3)."""
    payload = sources_payload(
        [
            {
                "document_id": "an_phu_profile",
                "chunk_index": 0,
                "similarity_score": 0.8,
                "text": "Trang thông tin: https://phuonganphu.gov.vn\nĐịa chỉ: Số 9",
                "citation": "Thông tin liên hệ và giờ làm việc của UBND phường An Phú",
            }
        ]
    )

    assert "http" not in payload[0]["text"]
    assert "Địa chỉ: Số 9" in payload[0]["text"]


def test_payload_handles_empty_input():
    assert sources_payload(None) == []
    assert sources_payload([]) == []
