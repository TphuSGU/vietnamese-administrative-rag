"""Retrieval and answer evaluation utilities."""

from app.rag.evaluation.evaluator import (
    AnswerEvaluation,
    AnswerEvaluator,
    DatasetError,
    EvaluationExample,
    RetrievalEvaluator,
    format_report,
    load_dataset,
    save_json,
)
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

__all__ = [
    "AnswerEvaluation",
    "AnswerEvaluator",
    "DatasetError",
    "EvaluationExample",
    "RetrievalEvaluator",
    "aggregate_per_k",
    "average_precision",
    "chunk_key",
    "first_relevant_rank",
    "format_report",
    "hit_rate_at_k",
    "load_dataset",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "save_json",
    "summarize",
]
