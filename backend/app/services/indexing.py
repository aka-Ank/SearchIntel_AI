from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.url_security import UrlSafetyPolicy, validate_crawl_url
from app.crawler.fetcher import Fetcher, FetchResponse
from app.crawler.parser import parse_html
from app.processing.chunking import StructureAwareChunker
from app.repositories.pages import ChunkRepository, PageRepository
from app.retrieval.service import RetrievalService
from app.schemas.indexing import IndexUrlResponse


class InlineHtmlFetcher:
    def __init__(self, html: str) -> None:
        self._html = html

    async def fetch(self, url: str) -> FetchResponse:
        safe_url = validate_crawl_url(url, UrlSafetyPolicy())
        return FetchResponse(
            url=safe_url,
            status_code=200,
            content_type="text/html",
            text=self._html,
        )


class IndexingService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        fetcher: Fetcher,
        chunker: StructureAwareChunker,
        retrieval_service: RetrievalService,
    ) -> None:
        self._session_factory = session_factory
        self._fetcher = fetcher
        self._chunker = chunker
        self._retrieval_service = retrieval_service

    async def index_url(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_id: str,
        url: str,
        html: str | None = None,
    ) -> IndexUrlResponse:
        fetcher: Fetcher = InlineHtmlFetcher(html) if html is not None else self._fetcher
        fetched = await fetcher.fetch(url)
        return self.index_fetched_page(
            tenant_id=tenant_id,
            project_id=project_id,
            website_id=website_id,
            fetched=fetched,
            normalized_url=validate_crawl_url(url, UrlSafetyPolicy()),
        )

    def index_fetched_page(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_id: str,
        fetched: FetchResponse,
        normalized_url: str,
    ) -> IndexUrlResponse:
        if "html" not in fetched.content_type.lower():
            raise ValueError(f"Unsupported content type: {fetched.content_type}")

        parsed = parse_html(fetched.url, fetched.text)
        x_robots = next(
            (value for key, value in fetched.headers.items() if key.lower() == "x-robots-tag"),
            None,
        )
        if x_robots:
            parsed.audit_data["x_robots_tag"] = x_robots
        with self._session_factory() as session:
            page_repo = PageRepository(session)
            chunk_repo = ChunkRepository(session)
            page, changed = page_repo.upsert_parsed_page(
                tenant_id=tenant_id,
                project_id=project_id,
                website_id=website_id,
                fetched_url=fetched.url,
                normalized_url=normalized_url,
                status_code=fetched.status_code,
                content_type=fetched.content_type,
                parsed=parsed,
            )
            chunks = self._chunker.chunk_page(
                tenant_id=tenant_id,
                project_id=project_id,
                website_id=website_id,
                page_id=page.id,
                page=parsed,
            )
            if changed:
                chunk_repo.replace_for_page(page_id=page.id, chunks=chunks)
                self._retrieval_service.index_chunks(chunks)
            session.commit()
            return IndexUrlResponse(
                page_id=page.id,
                url=page.url,
                title=page.title,
                chunk_count=len(chunks),
            )
