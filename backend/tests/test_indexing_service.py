from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.crawler.fetcher import StaticHtmlFetcher
from app.embeddings.providers import HashEmbeddingProvider
from app.models.page import ContentChunk as ContentChunkModel
from app.processing.chunking import StructureAwareChunker
from app.retrieval.bm25 import BM25Index
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore
from app.schemas.retrieval import RetrievalStrategy
from app.services.indexing import IndexingService

FIXTURE = Path(__file__).parent / "fixtures" / "sample_page.html"


class CountingVectorStore(InMemoryVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.upsert_count = 0

    def upsert(self, chunk, vector, *, metadata) -> None:
        self.upsert_count += 1
        super().upsert(chunk, vector, metadata=metadata)


@pytest.mark.anyio
async def test_index_url_makes_content_searchable(
    session_factory: sessionmaker[Session],
) -> None:
    retrieval = RetrievalService(
        embedding_provider=HashEmbeddingProvider(dimensions=64),
        vector_store=InMemoryVectorStore(),
        bm25_index=BM25Index(),
    )
    service = IndexingService(
        session_factory=session_factory,
        fetcher=StaticHtmlFetcher({"https://example.com/javascript-seo": FIXTURE.read_text()}),
        chunker=StructureAwareChunker(target_chars=220),
        retrieval_service=retrieval,
    )

    indexed = await service.index_url(
        tenant_id="tenant-a",
        project_id="project-a",
        website_id="site-a",
        url="https://example.com/javascript-seo",
    )

    assert indexed.chunk_count > 0
    response = retrieval.search(
        tenant_id="tenant-a",
        project_id="project-a",
        query="hydration strategy",
        strategy=RetrievalStrategy.hybrid,
        top_k=3,
    )
    assert response.results
    assert response.results[0].url == "https://example.com/javascript-seo"
    with session_factory() as session:
        chunk_count = len(session.scalars(select(ContentChunkModel)).all())
    assert chunk_count == indexed.chunk_count


@pytest.mark.anyio
async def test_unchanged_page_skips_vector_reindex(
    session_factory: sessionmaker[Session],
) -> None:
    vector_store = CountingVectorStore()
    retrieval = RetrievalService(
        embedding_provider=HashEmbeddingProvider(dimensions=64),
        vector_store=vector_store,
        bm25_index=BM25Index(),
    )
    service = IndexingService(
        session_factory=session_factory,
        fetcher=StaticHtmlFetcher({"https://example.com/javascript-seo": FIXTURE.read_text()}),
        chunker=StructureAwareChunker(target_chars=220),
        retrieval_service=retrieval,
    )

    first = await service.index_url(
        tenant_id="tenant-a",
        project_id="project-a",
        website_id="site-a",
        url="https://example.com/javascript-seo",
    )
    first_upserts = vector_store.upsert_count
    second = await service.index_url(
        tenant_id="tenant-a",
        project_id="project-a",
        website_id="site-a",
        url="https://example.com/javascript-seo",
    )

    assert first.page_id == second.page_id
    assert first_upserts > 0
    assert vector_store.upsert_count == first_upserts
