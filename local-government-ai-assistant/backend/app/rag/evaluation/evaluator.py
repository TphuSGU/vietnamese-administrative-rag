"""
Evaluation harness for the local-government RAG assistant.

The harness has two independent layers:

1. Retrieval evaluation (always available): Precision@K, Recall@K,
   HitRate@K, MRR and nDCG@K over chunk-level ground truth.
2. Answer evaluation (optional, ``--answer-eval``): checks citations,
   expected-term coverage and abstention without calling another LLM.

Datasets are JSONL files; one example per line. Minimal example::

    {"id": "q001",
     "question": "Ủy ban nhân dân cấp huyện chuyển giao thẩm quyền gì?",
     "expected_answer": "...",
     "relevant_chunks": ["151-2025-ND-CP#8", "151-2025-ND-CP#9"],
     "relevant_documents": ["151-2025-ND-CP"],
     "expected_citations": ["151/2025/NĐ-CP, Điều 4"],
     "answer_type": "factual",
     "difficulty": "easy"}

``relevant_chunks`` may also be objects:
``{"document_id": "151-2025-ND-CP", "chunk_index": 8}``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.models.data_models import EvaluationReport
from app.rag.evaluation.metrics import (
    aggregate_per_k,
    average_precision,
    chunk_key,
    first_relevant_rank,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    summarize,
)


class DatasetError(ValueError):
    """Raised when an evaluation dataset is missing or malformed."""


@dataclass
class EvaluationExample:
    """One question with its chunk-level ground truth."""

    id: str
    question: str
    relevant_chunks: List[str]
    expected_answer: str = ""
    relevant_documents: List[str] = field(default_factory=list)
    expected_citations: List[str] = field(default_factory=list)
    answer_type: str = "factual"
    difficulty: str = "medium"
    source_url: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise DatasetError("Example is missing 'id'")
        if not self.question.strip():
            raise DatasetError(f"Example {self.id} is missing 'question'")
        if not self.relevant_chunks:
            raise DatasetError(f"Example {self.id} needs at least one relevant chunk")
        if not self.relevant_documents:
            self.relevant_documents = sorted(
                {key.split("#", 1)[0] for key in self.relevant_chunks}
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationExample":
        """Parse one JSONL object, normalising both chunk label formats."""
        raw_chunks = data.get("relevant_chunks") or []
        normalised: List[str] = []
        for item in raw_chunks:
            if isinstance(item, str):
                if "#" not in item:
                    raise DatasetError(
                        f"Example {data.get('id')}: chunk '{item}' must look like "
                        "'<document_id>#<chunk_index>'"
                    )
                normalised.append(item.strip())
            elif isinstance(item, dict):
                try:
                    normalised.append(
                        chunk_key(item["document_id"], item["chunk_index"])
                    )
                except KeyError as exc:
                    raise DatasetError(
                        f"Example {data.get('id')}: chunk object missing {exc}"
                    ) from exc
            else:
                raise DatasetError(
                    f"Example {data.get('id')}: unsupported relevant chunk {item!r}"
                )

        return cls(
            id=str(data["id"]),
            question=str(data["question"]),
            relevant_chunks=normalised,
            expected_answer=str(data.get("expected_answer", "")),
            relevant_documents=[
                str(doc) for doc in (data.get("relevant_documents") or [])
            ],
            expected_citations=[
                str(citation) for citation in (data.get("expected_citations") or [])
            ],
            answer_type=str(data.get("answer_type", "factual")),
            difficulty=str(data.get("difficulty", "medium")),
            source_url=str(data.get("source_url", "")),
            notes=str(data.get("notes", "")),
        )


def load_dataset(path: Path | str) -> List[EvaluationExample]:
    """Load a JSONL dataset (or a JSON array) and validate it."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise DatasetError(f"Dataset not found: {dataset_path}")

    if dataset_path.suffix.lower() == ".json":
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
        records = raw if isinstance(raw, list) else raw.get("examples", [])
    else:
        records = []
        for line_number, line in enumerate(
            dataset_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise DatasetError(
                    f"{dataset_path}:{line_number}: invalid JSON ({exc})"
                ) from exc

    if not records:
        raise DatasetError(f"Dataset is empty: {dataset_path}")

    examples = [EvaluationExample.from_dict(record) for record in records]

    seen: set[str] = set()
    for example in examples:
        if example.id in seen:
            raise DatasetError(f"Duplicate example id: {example.id}")
        seen.add(example.id)

    return examples


def _retrieved_keys(chunks: Iterable[Any]) -> List[str]:
    return [chunk_key(chunk.document_id, chunk.chunk_index) for chunk in chunks]


class RetrievalEvaluator:
    """Compute chunk-level retrieval metrics for a retriever."""

    def __init__(
        self,
        retriever: Any,
        ks: Sequence[int] = (1, 3, 5, 10),
    ) -> None:
        if not ks:
            raise ValueError("At least one K value is required")
        if any(k <= 0 for k in ks):
            raise ValueError("K values must be positive")
        self.retriever = retriever
        self.ks = tuple(sorted(set(int(k) for k in ks)))
        self.max_k = max(self.ks)

    def evaluate(self, examples: Sequence[EvaluationExample]) -> EvaluationReport:
        """Run retrieval for every example and aggregate the metrics."""
        if not examples:
            raise DatasetError("Cannot evaluate an empty dataset")

        per_query: List[Dict[str, Any]] = []
        per_query_metrics: List[Dict[str, Any]] = []

        for example in examples:
            chunks = self.retriever.retrieve(example.question, k=self.max_k)
            retrieved_keys = _retrieved_keys(chunks)
            relevant = set(example.relevant_chunks)

            metrics: Dict[str, Any] = {
                "precision": {},
                "recall": {},
                "hit_rate": {},
                "ndcg": {},
            }
            for k in self.ks:
                metrics["precision"][k] = precision_at_k(
                    retrieved_keys, relevant, k
                )
                metrics["recall"][k] = recall_at_k(retrieved_keys, relevant, k)
                metrics["hit_rate"][k] = hit_rate_at_k(
                    retrieved_keys, relevant, k
                )
                metrics["ndcg"][k] = ndcg_at_k(retrieved_keys, relevant, k)

            metrics["mrr"] = reciprocal_rank(retrieved_keys, relevant)
            metrics["average_precision"] = average_precision(
                retrieved_keys, relevant
            )

            per_query_metrics.append(metrics)
            per_query.append(
                {
                    "id": example.id,
                    "question": example.question,
                    "difficulty": example.difficulty,
                    "answer_type": example.answer_type,
                    "relevant_chunks": sorted(relevant),
                    "retrieved_chunks": retrieved_keys,
                    "first_relevant_rank": first_relevant_rank(
                        retrieved_keys, relevant
                    ),
                    "document_hit": float(
                        bool(set(example.relevant_documents) & {
                            chunk.document_id for chunk in chunks
                        })
                    ),
                    "metrics": metrics,
                    "retrieved_details": [
                        {
                            "document_id": chunk.document_id,
                            "chunk_index": chunk.chunk_index,
                            "score": round(float(chunk.similarity_score), 6),
                            "heading_context": chunk.heading_context,
                            "text_preview": chunk.text[:220],
                        }
                        for chunk in chunks
                    ],
                }
            )

        metrics_by_k = aggregate_per_k(per_query_metrics, self.ks)
        metrics_by_k["document_hit_rate"] = summarize(
            [row["document_hit"] for row in per_query]
        )

        return EvaluationReport(
            dataset_size=len(examples),
            metrics_by_k=metrics_by_k,
            per_query_results=per_query,
        )


def format_report(report: EvaluationReport, ks: Sequence[int]) -> str:
    """Render a compact, human-readable summary."""
    lines = [
        f"Evaluation Report ({report.dataset_size} queries)",
        "=" * 58,
    ]
    for k in sorted(ks):
        metrics = report.metrics_by_k.get(k, {})
        lines.append(f"\nK = {k}")
        for name in ("precision", "recall", "hit_rate", "ndcg"):
            if name in metrics:
                value = metrics[name]
                lines.append(
                    f"  {name.replace('_', ' ').title():<12} "
                    f"{value['mean']:.3f} ± {value['std']:.3f}"
                )

    mrr = report.metrics_by_k.get("mrr")
    if mrr:
        lines.append(f"\nMRR          {mrr['mean']:.3f} ± {mrr['std']:.3f}")
    map_score = report.metrics_by_k.get("map")
    if map_score:
        lines.append(f"MAP          {map_score['mean']:.3f} ± {map_score['std']:.3f}")
    doc_hit = report.metrics_by_k.get("document_hit_rate")
    if doc_hit:
        lines.append(
            f"Doc HitRate  {doc_hit['mean']:.3f} ± {doc_hit['std']:.3f}"
        )
    return "\n".join(lines)


_ANSWER_STOPWORDS = {
    "và", "của", "các", "có", "được", "theo", "trong", "cho", "với", "là",
    "một", "những", "khi", "thì", "phải", "không", "này", "đó", "tại",
    "trên", "về", "để", "từ", "hoặc", "như", "ra", "vào", "đã", "sẽ",
    "đang", "bị", "do", "nếu", "mà", "thuộc", "quy", "định",
}


def _content_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[0-9a-zà-ỹ]+", text.lower())
    return {
        token for token in tokens
        if len(token) > 2 and token not in _ANSWER_STOPWORDS
    }


@dataclass
class AnswerEvaluation:
    """Deterministic answer-quality signals (no external judge required)."""

    per_query: List[Dict[str, Any]]
    summary: Dict[str, Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {"summary": self.summary, "per_query": self.per_query}


class AnswerEvaluator:
    """Evaluate generated answers against expected answers and citations."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline

    def evaluate(
        self,
        examples: Sequence[EvaluationExample],
        k: int = 5,
    ) -> AnswerEvaluation:
        per_query: List[Dict[str, Any]] = []

        for example in examples:
            response = self.pipeline.query(example.question, k=k)
            answer = response.answer or ""
            cited_keys = [
                chunk_key(chunk.document_id, chunk.chunk_index)
                for chunk in response.source_chunks
            ]
            cited_set = set(cited_keys)
            relevant = set(example.relevant_chunks)

            expected_tokens = _content_tokens(example.expected_answer)
            answer_tokens = _content_tokens(answer)
            term_recall = (
                len(expected_tokens & answer_tokens) / len(expected_tokens)
                if expected_tokens else 0.0
            )
            citation_precision = (
                len(cited_set & relevant) / len(cited_set) if cited_set else 0.0
            )
            citation_recall = (
                len(cited_set & relevant) / len(relevant) if relevant else 0.0
            )

            lowered = answer.lower()
            abstained = any(
                marker in lowered
                for marker in (
                    "không tìm thấy",
                    "không đủ thông tin",
                    "không có thông tin",
                )
            )

            per_query.append(
                {
                    "id": example.id,
                    "question": example.question,
                    "answer": answer,
                    "expected_answer": example.expected_answer,
                    "cited_chunks": cited_keys,
                    "citation_precision": citation_precision,
                    "citation_recall": citation_recall,
                    "expected_term_recall": term_recall,
                    "abstained": abstained,
                    "answer_length": len(answer),
                    "processing_time": response.processing_time,
                }
            )

        summary = {
            "citation_precision": summarize(
                [row["citation_precision"] for row in per_query]
            ),
            "citation_recall": summarize(
                [row["citation_recall"] for row in per_query]
            ),
            "expected_term_recall": summarize(
                [row["expected_term_recall"] for row in per_query]
            ),
            "abstention_rate": summarize(
                [float(row["abstained"]) for row in per_query]
            ),
        }
        return AnswerEvaluation(per_query=per_query, summary=summary)


def save_json(payload: Dict[str, Any], path: Path | str) -> None:
    """Write a report to disk, creating parent directories when needed."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
