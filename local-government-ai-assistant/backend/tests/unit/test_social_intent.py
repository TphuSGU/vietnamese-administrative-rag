"""Greetings must not retrieve/cite arbitrary legal chunks."""

from pathlib import Path
from unittest.mock import Mock

from app.rag.generation.social_intent import social_answer
from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline


def test_greeting_returns_welcome_without_codes():
    answer = social_answer("xin chào, bạn có thể giúp gì cho tôi?")
    assert answer
    assert "mã 1." not in answer.lower()
    assert "Nghị quyết" not in answer


def test_thanks_returns_short_reply():
    assert social_answer("cảm ơn bạn") == "Không có gì. Nếu cần tra cứu thêm thủ tục hoặc văn bản, bạn cứ hỏi tôi."


def test_legal_question_is_not_social():
    assert social_answer("Thủ tục đăng ký khai sinh cần giấy tờ gì?") == ""


def test_greeting_skips_retrieval_and_llm(tmp_path: Path):
    retriever = Mock()
    llm = Mock()
    validator = Mock()
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    response = pipeline.query("xin chào, bạn có thể giúp gì cho tôi?", k=5)

    retriever.retrieve.assert_not_called()
    llm.generate_answer.assert_not_called()
    validator.validate.assert_not_called()
    assert response.source_chunks == []
    assert "mã 1." not in response.answer.lower()
