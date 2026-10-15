import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.url_security import UrlSafetyPolicy
from app.crawler.fetcher import StaticHtmlFetcher
from app.crawler.site_crawler import WebsiteCrawler
from app.embeddings.providers import HashEmbeddingProvider
from app.models.common import WebsiteType
from app.models.page import ContentChunk
from app.processing.chunking import StructureAwareChunker
from app.repositories.pages import ChunkRepository
from app.repositories.projects import ProjectRepository
from app.repositories.websites import WebsiteRepository
from app.retrieval.bm25 import BM25Index
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore
from app.schemas.retrieval import RetrievalStrategy
from app.services.crawling import CrawlService
from app.services.indexing import IndexingService

SITE = {
    "https://example.com/": """
    <html><head><title>Home</title></head><body>
      <h1>Home</h1><p>Technical SEO hub content.</p>
      <a href="/javascript-seo">JavaScript SEO</a>
    </body></html>
    """,
    "https://example.com/javascript-seo": """
    <html><head><title>JavaScript SEO</title></head><body>
      <h1>JavaScript SEO</h1><p>Hydration and rendering advice.</p>
    </body></html>
    """,
}


@pytest.mark.anyio
async def test_crawl_service_persists_pages_chunks_and_searches(
    session_factory: sessionmaker[Session],
) -> None:
    vector_store = InMemoryVectorStore()
    retrieval = RetrievalService(
        embedding_provider=HashEmbeddingProvider(dimensions=64),
        vector_store=vector_store,
        bm25_index=BM25Index(),
        persisted_chunk_loader=lambda tenant_id, project_id, website_ids: _load_chunks(
            session_factory, tenant_id, project_id, website_ids
        ),
    )
    indexing = IndexingService(
        session_factory=session_factory,
        fetcher=StaticHtmlFetcher(SITE),
        chunker=StructureAwareChunker(target_chars=200),
        retrieval_service=retrieval,
    )
    crawling = CrawlService(
        session_factory=session_factory,
        crawler=WebsiteCrawler(
            fetcher=StaticHtmlFetcher(SITE),
            safety_policy=UrlSafetyPolicy(allow_local_urls=False),
        ),
        indexing_service=indexing,
    )
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="Site")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.com/",
            website_type=WebsiteType.own,
        )
        session.commit()

    job = await crawling.crawl_website(
        tenant_id="tenant-a",
        website_id=website.id,
        max_pages=5,
        max_depth=1,
        concurrency=2,
    )

    assert job is not None
    assert job.status == "COMPLETED"
    assert job.pages_crawled == 2
    with session_factory() as session:
        assert len(session.scalars(select(ContentChunk)).all()) >= 2

    response = retrieval.search(
        tenant_id="tenant-a",
        project_id=project.id,
        query="hydration rendering",
        strategy=RetrievalStrategy.hybrid,
        top_k=3,
    )
    assert response.results
    assert response.results[0].url == "https://example.com/javascript-seo"


def _load_chunks(
    session_factory: sessionmaker[Session],
    tenant_id: str,
    project_id: str,
    website_ids: list[str] | None,
):
    with session_factory() as session:
        repo = ChunkRepository(session)
        models = repo.list_for_project(
            tenant_id=tenant_id,
            project_id=project_id,
            website_ids=website_ids,
        )
        return [
            repo.to_schema(model, url=model.page.url, title=model.page.title) for model in models
        ]
