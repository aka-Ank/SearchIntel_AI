from app.embeddings.providers import HashEmbeddingProvider
from app.retrieval.bm25 import BM25Index
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore
from app.schemas.content import ContentChunk
from app.schemas.retrieval import RetrievalStrategy


def make_service() -> RetrievalService:
    return RetrievalService(
        embedding_provider=HashEmbeddingProvider(dimensions=64),
        vector_store=InMemoryVectorStore(),
        bm25_index=BM25Index(),
    )


def make_chunk(
    chunk_id: str,
    tenant_id: str,
    project_id: str,
    text: str,
) -> ContentChunk:
    return ContentChunk(
        id=chunk_id,
        tenant_id=tenant_id,
        project_id=project_id,
        website_id="site",
        page_id=f"page-{chunk_id}",
        url=f"https://example.com/{chunk_id}",
        title=f"Title {chunk_id}",
        heading_path=[],
        chunk_index=0,
        text=text,
        char_count=len(text),
    )


def test_bm25_finds_exact_seo_terms() -> None:
    service = make_service()
    service.index_chunks(
        [
            make_chunk("a", "tenant-a", "project-a", "JavaScript SEO rendering and hydration"),
            make_chunk("b", "tenant-a", "project-a", "Generic marketing homepage content"),
        ]
    )

    response = service.search(
        tenant_id="tenant-a",
        project_id="project-a",
        query="hydration",
        strategy=RetrievalStrategy.bm25,
        top_k=3,
    )

    assert response.results[0].chunk_id == "a"
    assert response.results[0].source_scores["bm25"] > 0


def test_hybrid_search_respects_tenant_isolation() -> None:
    service = make_service()
    service.index_chunks(
        [
            make_chunk("a", "tenant-a", "project-a", "JavaScript SEO rendering guide"),
            make_chunk("b", "tenant-b", "project-b", "Secret tenant competitor strategy"),
        ]
    )

    response = service.search(
        tenant_id="tenant-a",
        project_id="project-a",
        query="secret competitor strategy",
        strategy=RetrievalStrategy.hybrid,
        top_k=5,
    )

    assert all(result.tenant_id == "tenant-a" for result in response.results)
    assert {result.chunk_id for result in response.results} <= {"a"}


def test_vector_search_respects_project_and_website_filters() -> None:
    service = make_service()
    service.index_chunks(
        [
            make_chunk("a", "tenant-a", "project-a", "JavaScript SEO guide"),
            make_chunk("b", "tenant-a", "project-b", "JavaScript SEO private project"),
            make_chunk("c", "tenant-a", "project-a", "JavaScript SEO second website"),
        ]
    )

    # Override website ids for the filter check while keeping the helper compact.
    service._vector_store._records["a"][0].website_id = "site-a"  # type: ignore[attr-defined]
    service._vector_store._records["c"][0].website_id = "site-c"  # type: ignore[attr-defined]

    response = service.search(
        tenant_id="tenant-a",
        project_id="project-a",
        query="JavaScript SEO",
        strategy=RetrievalStrategy.vector,
        top_k=5,
        website_ids=["site-c"],
    )

    assert [result.chunk_id for result in response.results] == ["c"]
