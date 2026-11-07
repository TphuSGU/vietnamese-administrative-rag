"""Regression tests for pipeline fallback and retry metadata."""

from pathlib import Path
from unittest.mock import Mock

from app.models.data_models import GeneratedAnswer, RetrievedChunk
from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline


def _chunk(text="Nội dung"):
    return RetrievedChunk(text=text, similarity_score=0.9, metadata={})


def test_retry_keeps_locality_code(tmp_path: Path):
    retriever = Mock()
    retriever.retrieve.side_effect = [[_chunk()], [_chunk(), _chunk("Nội dung 2")]]
    llm = Mock()
    llm.generate_answer.return_value = GeneratedAnswer(
        answer="Câu trả lời có citation.",
        source_chunks=[],
        model="mock",
        tokens_used=5,
    )
    validator = Mock()
    validator.validate.side_effect = [(False, "evidence"), (True, None)]
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    pipeline.query("Câu hỏi kiểm thử hợp lệ", k=5, locality_code="25975")

    assert retriever.retrieve.call_args_list[0].kwargs["locality_code"] == "25975"
    assert retriever.retrieve.call_args_list[1].kwargs["locality_code"] == "25975"
    assert retriever.retrieve.call_args_list[1].kwargs["k"] == 10


def test_validation_failure_hides_internal_reason(tmp_path: Path):
    retriever = Mock()
    retriever.retrieve.return_value = [_chunk()]
    llm = Mock()
    llm.generate_answer.return_value = GeneratedAnswer(
        answer="Câu trả lời chưa đủ tin cậy.",
        source_chunks=[],
        model="mock",
        tokens_used=5,
    )
    validator = Mock()
    validator.validate.return_value = (False, "Citation check failed: secret")
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    response = pipeline.query("Câu hỏi kiểm thử hợp lệ", k=5)

    assert "Lý do:" not in response.answer
    assert "Citation check failed" not in response.answer


def _direct_llm_setup(retriever):
    llm = Mock()
    llm.MODEL_NAME = "mock"
    llm.generate_answer_without_context.return_value = GeneratedAnswer(
        answer=(
            "Tôi không tìm thấy thông tin trong tài liệu của địa phương "
            "cho câu hỏi này (nguồn tổng quát, không có trong tài liệu)."
        ),
        source_chunks=[],
        model="mock",
        tokens_used=12,
    )
    validator = Mock()
    validator.validate_direct.return_value = (True, None)
    return llm, validator


def test_empty_retrieval_falls_back_to_direct_llm(tmp_path: Path):
    retriever = Mock()
    retriever.retrieve.return_value = []
    llm, validator = _direct_llm_setup(retriever)
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    response = pipeline.query("Câu hỏi kiểm thử hợp lệ", k=5, locality_code="25975")

    llm.generate_answer_without_context.assert_called_once_with(
        "Câu hỏi kiểm thử hợp lệ"
    )
    llm.generate_answer.assert_not_called()
    assert "nguồn tổng quát" in response.answer
    assert response.source_chunks == []
    assert response.relevance_scores == []


def test_retrieval_error_falls_back_to_direct_llm(tmp_path: Path):
    retriever = Mock()
    retriever.retrieve.side_effect = Exception("vector store down")
    llm, validator = _direct_llm_setup(retriever)
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    # Không ném exception: vẫn trả lời được bằng LLM trực tiếp
    response = pipeline.query("Câu hỏi kiểm thử hợp lệ", k=5)

    llm.generate_answer_without_context.assert_called_once()
    assert "nguồn tổng quát" in response.answer


def test_direct_answer_failed_validation_hides_reason(tmp_path: Path):
    retriever = Mock()
    retriever.retrieve.return_value = []
    llm, validator = _direct_llm_setup(retriever)
    validator.validate_direct.return_value = (False, "Structure check failed: secret")
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm,
        output_validator=validator,
        log_dir=tmp_path,
    )

    response = pipeline.query("Câu hỏi kiểm thử hợp lệ", k=5)

    assert "secret" not in response.answer
    assert "Lý do:" not in response.answer
