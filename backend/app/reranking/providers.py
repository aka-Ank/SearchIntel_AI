from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.retrieval.fusion import FusedHit


@dataclass(frozen=True)
class RerankedHit:
    hit: FusedHit
    reranker_score: float | None


class Reranker(Protocol):
    def rerank(self, *, query: str, hits: list[FusedHit], top_k: int) -> list[RerankedHit]:
        """Rerank candidate hits."""


class NoOpReranker:
    def rerank(self, *, query: str, hits: list[FusedHit], top_k: int) -> list[RerankedHit]:
        return [RerankedHit(hit=hit, reranker_score=None) for hit in hits[:top_k]]


class CrossEncoderReranker:
    def __init__(self, *, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Install optional model dependencies with `pip install -e '.[models]'` "
                "to use cross-encoder reranking."
            ) from exc
        self._model = CrossEncoder(model_name)

    def rerank(self, *, query: str, hits: list[FusedHit], top_k: int) -> list[RerankedHit]:
        if not hits:
            return []
        pairs = [(query, hit.chunk.text) for hit in hits]
        scores = [float(score) for score in self._model.predict(pairs)]
        scored = [
            RerankedHit(hit=hit, reranker_score=score)
            for hit, score in zip(hits, scores, strict=True)
        ]
        ranked = sorted(
            scored,
            key=lambda item: (
                item.reranker_score if item.reranker_score is not None else item.hit.score
            ),
            reverse=True,
        )
        return ranked[:top_k]
