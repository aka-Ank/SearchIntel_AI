from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank
from app.retrieval.service import RetrievalService
from app.schemas.retrieval import RetrievalStrategy

METRIC_KEYS = ["precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"]


def run_retrieval_benchmark(
    *,
    retrieval_service: RetrievalService,
    tenant_id: str,
    project_id: str,
    data_path: Path,
    reports_dir: Path,
    k: int = 5,
) -> dict[str, object]:
    entries = json.loads(data_path.read_text())
    strategies = [
        RetrievalStrategy.bm25,
        RetrievalStrategy.dense,
        RetrievalStrategy.hybrid,
        RetrievalStrategy.hybrid_rerank,
    ]
    result_entries: list[dict[str, object]] = []
    summary: dict[str, dict[str, float]] = {}

    for strategy in strategies:
        metrics = []
        for entry in entries:
            response = retrieval_service.search(
                tenant_id=tenant_id,
                project_id=project_id,
                query=entry["question"],
                strategy=strategy,
                top_k=k,
            )
            retrieved = [result.page_id for result in response.results]
            relevant = set(entry["relevant_page_ids"])
            metrics.append(
                {
                    "question": entry["question"],
                    "strategy": strategy.value,
                    "precision_at_k": precision_at_k(retrieved, relevant, k),
                    "recall_at_k": recall_at_k(retrieved, relevant, k),
                    "mrr": reciprocal_rank(retrieved, relevant),
                    "ndcg_at_k": ndcg_at_k(retrieved, relevant, k),
                    "retrieved_page_ids": retrieved,
                }
            )
        summary[strategy.value] = _average_metrics(metrics)
        result_entries.extend(metrics)

    results: dict[str, object] = {"entries": result_entries, "summary": summary}
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "retrieval_benchmark.json").write_text(json.dumps(results, indent=2))
    (reports_dir / "retrieval_benchmark.md").write_text(_format_markdown(summary))
    return results


def _average_metrics(metrics: list[dict[str, object]]) -> dict[str, float]:
    if not metrics:
        return {"precision_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0}
    return {
        key: round(
            sum(_metric_value(metric, key) for metric in metrics) / len(metrics),
            4,
        )
        for key in METRIC_KEYS
    }


def _metric_value(metric: dict[str, object], key: str) -> float:
    value = metric[key]
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"Metric {key} is not numeric")


def _format_markdown(summary: dict[str, dict[str, float]]) -> str:
    lines = [
        "# Retrieval Benchmark",
        "",
        "| Strategy | Precision@K | Recall@K | MRR | NDCG@K |",
        "|---|---:|---:|---:|---:|",
    ]
    for strategy, metrics in summary.items():
        lines.append(
            f"| {strategy} | {metrics['precision_at_k']} | {metrics['recall_at_k']} | "
            f"{metrics['mrr']} | {metrics['ndcg_at_k']} |"
        )
    lines.append("")
    return "\n".join(lines)
