"""
Information-retrieval metrics for the RAG evaluation harness.

All metrics operate on *ranked chunk keys*. A chunk key has the form
``<document_id>#<chunk_index>`` (for example ``151-2025-ND-CP#8``), which is
stable across re-ingestion as long as the document and chunk order do not
change.

The functions are intentionally pure and dependency-free so they can be
unit-tested without loading ChromaDB or an embedding model.
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Sequence, Set


def chunk_key(document_id: str, chunk_index: int) -> str:
    """Build the canonical key used to compare retrieved and relevant chunks."""
    return f"{document_id}#{int(chunk_index)}"


def _top_k(retrieved: Sequence[str], k: int) -> List[str]:
    if k <= 0:
        return []
    return list(retrieved[:k])


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """
    Precision@K: fraction of the top-K results that are relevant.

    The denominator is ``k`` (not ``len(retrieved)``) so a retriever that
    returns fewer than K results is penalised.
    """
    if k <= 0:
        return 0.0
    relevant_set = set(relevant)
    top = _top_k(retrieved, k)
    return sum(1 for key in top if key in relevant_set) / k


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Recall@K: fraction of all relevant chunks found in the top-K results."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    top = _top_k(retrieved, k)
    return sum(1 for key in top if key in relevant_set) / len(relevant_set)


def hit_rate_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """HitRate@K: 1.0 when at least one relevant chunk appears in the top-K."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    return 1.0 if any(key in relevant_set for key in _top_k(retrieved, k)) else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """MRR contribution: 1 / rank of the first relevant chunk (1-indexed)."""
    relevant_set = set(relevant)
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant_set:
            return 1.0 / rank
    return 0.0


def first_relevant_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> int | None:
    """Return the 1-indexed rank of the first relevant chunk, or ``None``."""
    relevant_set = set(relevant)
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant_set:
            return rank
    return None


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """
    nDCG@K with binary relevance.

    DCG = sum(rel_i / log2(i + 2)) for i in 0..K-1
    IDCG uses min(|relevant|, K) ideal hits at the top positions.
    """
    relevant_set = set(relevant)
    if not relevant_set or k <= 0:
        return 0.0

    top = _top_k(retrieved, k)
    dcg = sum(
        1.0 / math.log2(rank + 2)
        for rank, key in enumerate(top)
        if key in relevant_set
    )
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    return dcg / idcg if idcg else 0.0


def average_precision(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Average precision over the full ranked list (useful for diagnostics)."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0

    hits = 0
    precision_sum = 0.0
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant_set:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / len(relevant_set)


def summarize(values: Sequence[float]) -> Dict[str, float]:
    """Return mean/std/count for a list of per-query metric values."""
    if not values:
        return {"mean": 0.0, "std": 0.0, "count": 0}
    return {
        "mean": mean(values),
        "std": pstdev(values),
        "count": len(values),
    }


def aggregate_per_k(
    per_query_metrics: Sequence[Dict[str, Any]],
    ks: Sequence[int],
) -> Dict[Any, Dict[str, Dict[str, float]]]:
    """
    Aggregate per-query metrics into the report shape used by ``EvaluationReport``.

    ``per_query_metrics`` is a list of dicts shaped like::

        {"precision": {1: 1.0, 3: 0.66}, "recall": {...}, "ndcg": {...},
         "hit_rate": {...}, "mrr": 0.5}
    """
    report: Dict[Any, Dict[str, Dict[str, float]]] = {}
    metric_names = ("precision", "recall", "hit_rate", "ndcg")

    for k in ks:
        report[k] = {}
        for name in metric_names:
            values = [row[name][k] for row in per_query_metrics if k in row[name]]
            report[k][name] = summarize(values)

    report["mrr"] = summarize([row["mrr"] for row in per_query_metrics])
    report["map"] = summarize([row["average_precision"] for row in per_query_metrics])
    return report
