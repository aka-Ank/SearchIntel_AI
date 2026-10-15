from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.content import ContentChunk


@dataclass(frozen=True)
class RankedInput:
    chunk: ContentChunk
    score: float
    source: str


@dataclass(frozen=True)
class FusedHit:
    chunk: ContentChunk
    score: float
    source_scores: dict[str, float]
    source_ranks: dict[str, int]
    reranker_score: float | None = None
    final_rank: int | None = None


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[RankedInput]],
    *,
    top_k: int,
    rank_constant: int = 60,
) -> list[FusedHit]:
    fused_scores: dict[str, float] = {}
    source_scores: dict[str, dict[str, float]] = {}
    source_ranks: dict[str, dict[str, int]] = {}
    chunks: dict[str, ContentChunk] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            chunks[item.chunk.id] = item.chunk
            fused_scores[item.chunk.id] = fused_scores.get(item.chunk.id, 0.0) + (
                1.0 / (rank_constant + rank)
            )
            source_scores.setdefault(item.chunk.id, {})[item.source] = item.score
            source_ranks.setdefault(item.chunk.id, {})[item.source] = rank

    ordered = sorted(fused_scores.items(), key=lambda value: value[1], reverse=True)
    return [
        FusedHit(
            chunk=chunks[chunk_id],
            score=score,
            source_scores=source_scores[chunk_id],
            source_ranks=source_ranks[chunk_id],
        )
        for chunk_id, score in ordered[:top_k]
    ]
