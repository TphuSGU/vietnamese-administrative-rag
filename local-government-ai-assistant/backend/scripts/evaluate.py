#!/usr/bin/env python3
"""
Evaluate retrieval (and optionally answers) on the golden question set.

Examples:
    python scripts/evaluate.py
    python scripts/evaluate.py --alpha 0.5 --k 1 3 5 10
    python scripts/evaluate.py --answer-eval --limit 10
    python scripts/evaluate.py --dataset evaluation/questions.jsonl \
        --output evaluation/results/baseline.json

The default dataset lives at ``backend/evaluation/questions.jsonl``.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import (  # noqa: E402
    get_embedding_service,
    get_llm_service,
    get_vector_store,
)
from app.core.logging import setup_logging  # noqa: E402
from app.rag.evaluation.evaluator import (  # noqa: E402
    AnswerEvaluator,
    RetrievalEvaluator,
    format_report,
    load_dataset,
    save_json,
)
from app.rag.generation.output_validator import OutputValidator  # noqa: E402
from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline  # noqa: E402
from app.rag.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402


DEFAULT_DATASET = BACKEND_DIR / "evaluation" / "questions.jsonl"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "evaluation" / "results"


def build_retriever(alpha: float, min_similarity: float) -> HybridRetriever:
    return HybridRetriever(
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
        alpha=alpha,
        min_similarity=min_similarity,
        use_reranking=settings.retrieval_use_reranking,
        bm25s_persist_dir=settings.bm25s_persist_dir,
    )


def build_pipeline(retriever: HybridRetriever) -> HybridRAGPipeline:
    return HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=get_llm_service(),
        output_validator=OutputValidator(
            min_evidence_ratio=0.25,
            strict_mode=False,
        ),
        log_dir=BACKEND_DIR / "logs",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG assistant")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"JSONL dataset (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--k",
        nargs="+",
        type=int,
        default=[1, 3, 5, 10],
        help="K values to report (default: 1 3 5 10)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.6,
        help="Vector weight in hybrid retrieval (default: 0.6)",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=settings.retrieval_min_similarity,
        help="Cosine threshold for vector candidates",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Evaluate only the first N examples (0 = all)",
    )
    parser.add_argument(
        "--answer-eval",
        action="store_true",
        help="Also generate answers and report citation/term metrics",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report path (default: evaluation/results/run_<timestamp>.json)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print only; do not write a JSON report",
    )
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0:
        parser.error("--alpha must be between 0 and 1")
    if any(k <= 0 for k in args.k):
        parser.error("--k values must be positive")

    setup_logging(settings.log_level)

    examples = load_dataset(args.dataset)
    if args.limit > 0:
        examples = examples[: args.limit]

    print(f"Dataset: {args.dataset} ({len(examples)} examples)")
    print(f"Config : alpha={args.alpha}, min_similarity={args.min_similarity}, k={args.k}")

    retriever = build_retriever(args.alpha, args.min_similarity)
    report = RetrievalEvaluator(retriever, ks=args.k).evaluate(examples)
    print()
    print(format_report(report, args.k))

    payload = report.to_dict()
    payload["config"] = {
        "dataset": str(args.dataset),
        "alpha": args.alpha,
        "min_similarity": args.min_similarity,
        "k": args.k,
        "limit": args.limit,
        "embedding_model": settings.embedding_model_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.answer_eval:
        print("\nGenerating answers (this calls Gemini)...")
        answer_result = AnswerEvaluator(build_pipeline(retriever)).evaluate(
            examples, k=max(args.k)
        )
        payload["answer_evaluation"] = answer_result.to_dict()
        print("\nAnswer evaluation")
        print("-" * 58)
        for name, value in answer_result.summary.items():
            print(
                f"  {name.replace('_', ' ').title():<24} "
                f"{value['mean']:.3f} ± {value['std']:.3f}"
            )

    if not args.no_save:
        output = args.output
        if output is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output = DEFAULT_OUTPUT_DIR / f"run_{stamp}.json"
        save_json(payload, output)
        print(f"\nReport saved: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
