from __future__ import annotations

import math


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    return len([item for item in top if item in relevant_ids]) / len(top)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top = retrieved_ids[:k]
    return len([item for item in top if item in relevant_ids]) / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for index, item in enumerate(retrieved_ids, start=1):
        if item in relevant_ids:
            return 1.0 / index
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = 0.0
    for index, item in enumerate(retrieved_ids[:k], start=1):
        if item in relevant_ids:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg
