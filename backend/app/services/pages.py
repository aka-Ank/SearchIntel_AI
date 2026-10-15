from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.repositories.pages import PageRepository
from app.schemas.pages import PageListItem, PageRead


class PageService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_pages(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_ids: list[str] | None = None,
    ) -> list[PageListItem]:
        with self._session_factory() as session:
            pages = PageRepository(session).list_for_project(
                tenant_id=tenant_id,
                project_id=project_id,
                website_ids=website_ids,
            )
            return [
                PageListItem(
                    id=page.id,
                    tenant_id=page.tenant_id,
                    project_id=page.project_id,
                    website_id=page.website_id,
                    url=page.url,
                    normalized_url=page.normalized_url,
                    title=page.title,
                    content_hash=page.content_hash,
                    word_count=page.word_count,
                    crawled_at=page.crawled_at,
                )
                for page in pages
            ]

    def get_page(self, *, tenant_id: str, page_id: str) -> PageRead | None:
        with self._session_factory() as session:
            page = PageRepository(session).get(tenant_id=tenant_id, page_id=page_id)
            if page is None:
                return None
            return PageRead(
                id=page.id,
                tenant_id=page.tenant_id,
                project_id=page.project_id,
                website_id=page.website_id,
                url=page.url,
                normalized_url=page.normalized_url,
                title=page.title,
                content_hash=page.content_hash,
                word_count=page.word_count,
                crawled_at=page.crawled_at,
                canonical_url=page.canonical_url,
                meta_description=page.meta_description,
                status_code=page.status_code,
                content_type=page.content_type,
                normalized_text=page.normalized_text,
            )
