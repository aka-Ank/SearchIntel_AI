from app.reranking.providers import NoOpReranker, RerankedHit
from app.retrieval.fusion import FusedHit
from app.schemas.content import ContentChunk


def chunk(chunk_id: str, text: str) -> ContentChunk:
    return ContentChunk(
        id=chunk_id,
        tenant_id="tenant",
        project_id="project",
        website_id="site",
        page_id=f"page-{chunk_id}",
        url=f"https://example.com/{chunk_id}",
        title=chunk_id,
        heading_path=[],
        chunk_index=0,
        text=text,
        char_count=len(text),
    )


def test_noop_reranker_preserves_order() -> None:
    hits = [
        FusedHit(chunk=chunk("a", "first"), score=0.4, source_scores={}, source_ranks={}),
        FusedHit(chunk=chunk("b", "second"), score=0.3, source_scores={}, source_ranks={}),
    ]

    reranked = NoOpReranker().rerank(query="anything", hits=hits, top_k=2)

    assert [item.hit.chunk.id for item in reranked] == ["a", "b"]
    assert all(item.reranker_score is None for item in reranked)


def test_mockable_reranker_can_reorder_fixture_hits() -> None:
    class FixtureReranker:
        def rerank(self, *, query: str, hits: list[FusedHit], top_k: int) -> list[RerankedHit]:
            return [
                RerankedHit(hit=hits[1], reranker_score=0.9),
                RerankedHit(hit=hits[0], reranker_score=0.1),
            ][:top_k]

    hits = [
        FusedHit(chunk=chunk("a", "first"), score=0.4, source_scores={}, source_ranks={}),
        FusedHit(chunk=chunk("b", "second"), score=0.3, source_scores={}, source_ranks={}),
    ]

    reranked = FixtureReranker().rerank(query="anything", hits=hits, top_k=2)

    assert [item.hit.chunk.id for item in reranked] == ["b", "a"]
    assert reranked[0].reranker_score == 0.9
