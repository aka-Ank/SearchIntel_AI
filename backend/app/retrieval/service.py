from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from app.embeddings.providers import EmbeddingProvider
from app.reranking.providers import NoOpReranker, Reranker
from app.retrieval.bm25 import BM25Index
from app.retrieval.fusion import FusedHit, RankedInput, reciprocal_rank_fusion
from app.retrieval.query_processing import QueryProcessor
from app.retrieval.vector_store import VectorStore
from app.schemas.content import ContentChunk
from app.schemas.retrieval import RetrievalStrategy, RetrievedChunkResult, SearchResponse

T = TypeVar("T")


class RetrievalService:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        persisted_chunk_loader: Callable[[str, str, list[str] | None], list[ContentChunk]]
        | None = None,
        query_processor: QueryProcessor | None = None,
        reranker: Reranker | None = None,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        fusion_top_k: int = 20,
        rerank_top_k: int = 8,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._bm25_index = bm25_index
        self._persisted_chunk_loader = persisted_chunk_loader
        self._query_processor = query_processor or QueryProcessor()
        self._reranker = reranker or NoOpReranker()
        self._bm25_top_k = bm25_top_k
        self._dense_top_k = dense_top_k
        self._fusion_top_k = fusion_top_k
        self._rerank_top_k = rerank_top_k

    def index_chunks(self, chunks: list[ContentChunk]) -> None:
        vectors = self._embedding_provider.embed_batch([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._vector_store.upsert(chunk, vector, metadata=self._embedding_provider.metadata)
            self._bm25_index.upsert(chunk)

    def search(
        self,
        *,
        tenant_id: str,
        project_id: str,
        query: str,
        strategy: RetrievalStrategy,
        top_k: int,
        website_ids: list[str] | None = None,
        include_debug: bool = False,
    ) -> SearchResponse:
        processed_query = self._query_processor.process(query)
        timings: dict[str, float] = {}

        if self._persisted_chunk_loader is not None and strategy in {
            RetrievalStrategy.bm25,
            RetrievalStrategy.hybrid,
            RetrievalStrategy.hybrid_rerank,
        }:
            chunks = self._persisted_chunk_loader(tenant_id, project_id, website_ids)
            self._bm25_index.rebuild(chunks)

        if strategy in {RetrievalStrategy.dense, RetrievalStrategy.vector}:
            hits = self._timed(
                timings,
                "dense_ms",
                lambda: self._vector_hits(
                    tenant_id,
                    project_id,
                    processed_query.semantic_query,
                    top_k,
                    website_ids,
                ),
            )
        elif strategy == RetrievalStrategy.bm25:
            hits = self._timed(
                timings,
                "bm25_ms",
                lambda: self._bm25_hits(
                    tenant_id,
                    project_id,
                    processed_query.lexical_query,
                    top_k,
                    website_ids,
                ),
            )
        else:
            hits = self._hybrid_hits(
                tenant_id,
                project_id,
                processed_query.lexical_query,
                processed_query.semantic_query,
                website_ids,
                timings,
            )
            if strategy == RetrievalStrategy.hybrid_rerank:
                hits = self._rerank_hits(processed_query.semantic_query, hits, top_k, timings)

        ranked_hits = _assign_final_ranks(hits[:top_k])
        return SearchResponse(
            query=processed_query.original_query,
            strategy=strategy,
            results=[
                _to_result(hit, include_debug=include_debug, timings=timings) for hit in ranked_hits
            ],
        )

    def _vector_hits(
        self,
        tenant_id: str,
        project_id: str,
        query: str,
        top_k: int,
        website_ids: list[str] | None,
    ) -> list[FusedHit]:
        query_vector = self._embedding_provider.embed_query(query)
        hits = self._vector_store.search(
            query_vector=query_vector,
            tenant_id=tenant_id,
            project_id=project_id,
            top_k=top_k,
            website_ids=website_ids,
            metadata=self._embedding_provider.metadata,
        )
        return [
            FusedHit(
                chunk=hit.chunk,
                score=hit.score,
                source_scores={"dense": hit.score},
                source_ranks={"dense": rank},
            )
            for rank, hit in enumerate(hits, start=1)
        ]

    def _bm25_hits(
        self,
        tenant_id: str,
        project_id: str,
        query: str,
        top_k: int,
        website_ids: list[str] | None,
    ) -> list[FusedHit]:
        hits = self._bm25_index.search(
            query=query,
            tenant_id=tenant_id,
            project_id=project_id,
            top_k=top_k,
            website_ids=website_ids,
        )
        return [
            FusedHit(
                chunk=hit.chunk,
                score=hit.score,
                source_scores={"bm25": hit.score},
                source_ranks={"bm25": rank},
            )
            for rank, hit in enumerate(hits, start=1)
        ]

    def _hybrid_hits(
        self,
        tenant_id: str,
        project_id: str,
        lexical_query: str,
        semantic_query: str,
        website_ids: list[str] | None,
        timings: dict[str, float],
    ) -> list[FusedHit]:
        dense_hits = self._timed(
            timings,
            "dense_ms",
            lambda: self._vector_hits(
                tenant_id,
                project_id,
                semantic_query,
                self._dense_top_k,
                website_ids,
            ),
        )
        bm25_hits = self._timed(
            timings,
            "bm25_ms",
            lambda: self._bm25_hits(
                tenant_id,
                project_id,
                lexical_query,
                self._bm25_top_k,
                website_ids,
            ),
        )
        return self._timed(
            timings,
            "fusion_ms",
            lambda: reciprocal_rank_fusion(
                [
                    [
                        RankedInput(chunk=hit.chunk, score=hit.score, source="dense")
                        for hit in dense_hits
                    ],
                    [
                        RankedInput(chunk=hit.chunk, score=hit.score, source="bm25")
                        for hit in bm25_hits
                    ],
                ],
                top_k=self._fusion_top_k,
            ),
        )

    def _rerank_hits(
        self,
        query: str,
        hits: list[FusedHit],
        top_k: int,
        timings: dict[str, float],
    ) -> list[FusedHit]:
        reranked = self._timed(
            timings,
            "reranker_ms",
            lambda: self._reranker.rerank(
                query=query,
                hits=hits,
                top_k=min(top_k, self._rerank_top_k),
            ),
        )
        return [
            FusedHit(
                chunk=item.hit.chunk,
                score=item.reranker_score if item.reranker_score is not None else item.hit.score,
                source_scores=item.hit.source_scores,
                source_ranks=item.hit.source_ranks,
                reranker_score=item.reranker_score,
            )
            for item in reranked
        ]

    def _timed(self, timings: dict[str, float], key: str, fn: Callable[[], T]) -> T:
        started = time.perf_counter()
        result = fn()
        timings[key] = round((time.perf_counter() - started) * 1000, 3)
        return result


def _assign_final_ranks(hits: list[FusedHit]) -> list[FusedHit]:
    return [
        FusedHit(
            chunk=hit.chunk,
            score=hit.score,
            source_scores=hit.source_scores,
            source_ranks=hit.source_ranks,
            reranker_score=hit.reranker_score,
            final_rank=rank,
        )
        for rank, hit in enumerate(hits, start=1)
    ]


def _to_result(
    hit: FusedHit,
    *,
    include_debug: bool,
    timings: dict[str, float],
) -> RetrievedChunkResult:
    chunk = hit.chunk
    debug: dict[str, float | int | str] = {}
    if include_debug:
        debug = {
            "chunk_id": chunk.id,
            "url": chunk.url,
            "rrf_score": hit.score,
            "final_rank": hit.final_rank or 0,
            **{f"{source}_score": value for source, value in hit.source_scores.items()},
            **{f"{source}_rank": value for source, value in hit.source_ranks.items()},
            **timings,
        }
        if hit.reranker_score is not None:
            debug["reranker_score"] = hit.reranker_score
    return RetrievedChunkResult(
        chunk_id=chunk.id,
        tenant_id=chunk.tenant_id,
        project_id=chunk.project_id,
        website_id=chunk.website_id,
        page_id=chunk.page_id,
        url=chunk.url,
        title=chunk.title,
        heading_path=chunk.heading_path,
        snippet=chunk.text[:280],
        content=chunk.text,
        score=hit.score,
        source_scores=hit.source_scores,
        debug=debug,
    )
