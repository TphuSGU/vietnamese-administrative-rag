"""Unit tests for retrieval metrics, dataset loading and the evaluator."""

import json
from types import SimpleNamespace

import pytest

from app.models.data_models import ChunkReference
from app.rag.evaluation.evaluator import (
    AnswerEvaluator,
    DatasetError,
    EvaluationExample,
    RetrievalEvaluator,
    load_dataset,
)
from app.rag.evaluation.metrics import (
    average_precision,
    chunk_key,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class FakeChunk:
    def __init__(self, document_id, chunk_index, score=1.0):
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.similarity_score = score
        self.heading_context = "Điều 1"
        self.text = "nội dung"


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def retrieve(self, query, k=5):
        self.calls.append((query, k))
        return self.chunks[:k]


class TestMetrics:
    def test_chunk_key(self):
        assert chunk_key("151-2025-ND-CP", 8) == "151-2025-ND-CP#8"

    def test_precision_recall_hit_rate(self):
        retrieved = ["a#1", "a#2", "b#1", "c#1"]
        relevant = {"a#1", "c#1", "d#1"}

        assert precision_at_k(retrieved, relevant, 2) == 0.5
        assert precision_at_k(retrieved, relevant, 4) == 0.5
        assert recall_at_k(retrieved, relevant, 2) == pytest.approx(1 / 3)
        assert recall_at_k(retrieved, relevant, 4) == pytest.approx(2 / 3)
        assert hit_rate_at_k(retrieved, relevant, 1) == 1.0
        assert hit_rate_at_k(retrieved, {"z#1"}, 4) == 0.0

    def test_mrr_uses_first_relevant_rank(self):
        assert reciprocal_rank(["a#1", "b#1", "c#1"], {"b#1"}) == 0.5
        assert reciprocal_rank(["a#1"], {"z#1"}) == 0.0

    def test_ndcg_rewards_relevant_items_at_the_top(self):
        relevant = {"a#1", "b#1"}
        good = ndcg_at_k(["a#1", "b#1", "c#1"], relevant, 3)
        bad = ndcg_at_k(["c#1", "a#1", "b#1"], relevant, 3)

        assert good == pytest.approx(1.0)
        assert 0.0 < bad < good

    def test_ndcg_without_relevant_is_zero(self):
        assert ndcg_at_k(["a#1"], set(), 3) == 0.0
        assert ndcg_at_k([], {"a#1"}, 3) == 0.0

    def test_average_precision(self):
        retrieved = ["a#1", "x#1", "b#1"]
        relevant = {"a#1", "b#1"}
        # AP = (1/1 + 2/3) / 2
        assert average_precision(retrieved, relevant) == pytest.approx(5 / 6)


class TestDatasetLoading:
    def test_loads_jsonl_and_normalises_chunk_objects(self, tmp_path):
        path = tmp_path / "questions.jsonl"
        path.write_text(
            json.dumps(
                {
                    "id": "q1",
                    "question": "Câu hỏi?",
                    "relevant_chunks": [
                        "151-2025-ND-CP#8",
                        {"document_id": "151-2025-ND-CP", "chunk_index": 9},
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        examples = load_dataset(path)

        assert len(examples) == 1
        assert examples[0].relevant_chunks == [
            "151-2025-ND-CP#8",
            "151-2025-ND-CP#9",
        ]
        assert examples[0].relevant_documents == ["151-2025-ND-CP"]

    def test_rejects_duplicate_ids(self, tmp_path):
        path = tmp_path / "questions.jsonl"
        row = json.dumps(
            {
                "id": "dup",
                "question": "Câu hỏi?",
                "relevant_chunks": ["a#1"],
            }
        )
        path.write_text(row + "\n" + row + "\n", encoding="utf-8")

        with pytest.raises(DatasetError, match="Duplicate"):
            load_dataset(path)

    def test_rejects_missing_relevant_chunks(self):
        with pytest.raises(DatasetError, match="relevant chunk"):
            EvaluationExample(id="q1", question="Câu hỏi?", relevant_chunks=[])


class TestRetrievalEvaluator:
    def test_aggregates_metrics_and_per_query_details(self):
        examples = [
            EvaluationExample(
                id="q1",
                question="Câu hỏi một?",
                relevant_chunks=["a#1", "b#1"],
            ),
            EvaluationExample(
                id="q2",
                question="Câu hỏi hai?",
                relevant_chunks=["c#1"],
            ),
        ]
        retriever = FakeRetriever(
            [FakeChunk("a", 1), FakeChunk("x", 1), FakeChunk("b", 1)]
        )

        report = RetrievalEvaluator(retriever, ks=(1, 3)).evaluate(examples)

        assert report.dataset_size == 2
        assert report.metrics_by_k[1]["precision"]["mean"] == 0.5
        assert report.metrics_by_k[3]["recall"]["mean"] == pytest.approx(0.5)
        assert report.metrics_by_k["mrr"]["mean"] == pytest.approx(0.5)
        assert report.metrics_by_k["document_hit_rate"]["mean"] == 0.5
        assert report.per_query_results[0]["first_relevant_rank"] == 1
        assert report.per_query_results[1]["first_relevant_rank"] is None
        assert retriever.calls[0] == ("Câu hỏi một?", 3)

    def test_empty_dataset_is_rejected(self):
        with pytest.raises(DatasetError):
            RetrievalEvaluator(FakeRetriever([])).evaluate([])


class TestAnswerEvaluator:
    def test_citation_and_term_metrics(self):
        example = EvaluationExample(
            id="q1",
            question="Câu hỏi?",
            relevant_chunks=["a#1"],
            expected_answer="Thẩm quyền cấp huyện chuyển giao cho chủ tịch tỉnh.",
        )
        response = SimpleNamespace(
            answer="Thẩm quyền cấp huyện chuyển giao cho chủ tịch tỉnh.",
            source_chunks=[ChunkReference("a", "text", 1.0, 1)],
            processing_time=0.01,
        )
        pipeline = SimpleNamespace(query=lambda question, k=5: response)

        result = AnswerEvaluator(pipeline).evaluate([example], k=1)

        assert result.per_query[0]["citation_precision"] == 1.0
        assert result.per_query[0]["citation_recall"] == 1.0
        assert result.per_query[0]["expected_term_recall"] > 0.5
        assert result.summary["abstention_rate"]["mean"] == 0.0
