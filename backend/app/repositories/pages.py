from __future__ import annotations

import hashlib

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.common import utc_now
from app.models.page import ContentChunk as ContentChunkModel
from app.models.page import Page
from app.schemas.content import ContentChunk, ParsedPage


class PageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_parsed_page(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_id: str,
        fetched_url: str,
        normalized_url: str,
        status_code: int,
        content_type: str,
        parsed: ParsedPage,
    ) -> tuple[Page, bool]:
        existing = self.get_by_normalized_url(
            tenant_id=tenant_id,
            website_id=website_id,
            normalized_url=normalized_url,
        )
        now = utc_now()
        word_count = len(parsed.body_text.split())

        if existing is not None:
            changed = existing.content_hash != parsed.content_hash
            existing.url = fetched_url
            existing.canonical_url = parsed.canonical_url
            existing.title = parsed.title
            existing.meta_description = parsed.meta_description
            existing.status_code = status_code
            existing.content_type = content_type
            existing.normalized_text = parsed.body_text
            existing.content_hash = parsed.content_hash
            existing.word_count = word_count
            existing.audit_data = parsed.audit_data
            existing.crawled_at = now
            self.session.flush()
            return existing, changed

        page = Page(
            tenant_id=tenant_id,
            project_id=project_id,
            website_id=website_id,
            url=fetched_url,
            normalized_url=normalized_url,
            canonical_url=parsed.canonical_url,
            title=parsed.title,
            meta_description=parsed.meta_description,
            status_code=status_code,
            content_type=content_type,
            normalized_text=parsed.body_text,
            content_hash=parsed.content_hash,
            word_count=word_count,
            audit_data=parsed.audit_data,
            crawled_at=now,
        )
        self.session.add(page)
        self.session.flush()
        return page, True

    def get(self, *, tenant_id: str, page_id: str) -> Page | None:
        return self.session.scalar(
            select(Page).where(Page.id == page_id, Page.tenant_id == tenant_id)
        )

    def get_by_normalized_url(
        self,
        *,
        tenant_id: str,
        website_id: str,
        normalized_url: str,
    ) -> Page | None:
        return self.session.scalar(
            select(Page).where(
                Page.tenant_id == tenant_id,
                Page.website_id == website_id,
                Page.normalized_url == normalized_url,
            )
        )

    def list_for_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_ids: list[str] | None = None,
    ) -> list[Page]:
        statement = select(Page).where(Page.tenant_id == tenant_id, Page.project_id == project_id)
        if website_ids:
            statement = statement.where(Page.website_id.in_(website_ids))
        return list(self.session.scalars(statement.order_by(Page.url)))


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_page(
        self,
        *,
        page_id: str,
        chunks: list[ContentChunk],
    ) -> list[ContentChunkModel]:
        self.session.execute(delete(ContentChunkModel).where(ContentChunkModel.page_id == page_id))
        models: list[ContentChunkModel] = []
        for chunk in chunks:
            model = ContentChunkModel(
                id=chunk.id,
                tenant_id=chunk.tenant_id,
                project_id=chunk.project_id,
                website_id=chunk.website_id,
                page_id=chunk.page_id,
                chunk_index=chunk.chunk_index,
                heading_path=chunk.heading_path,
                content=chunk.text,
                content_hash=hashlib.sha256(chunk.text.encode()).hexdigest(),
                character_count=chunk.char_count,
            )
            self.session.add(model)
            models.append(model)
        self.session.flush()
        return models

    def list_for_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_ids: list[str] | None = None,
    ) -> list[ContentChunkModel]:
        statement = select(ContentChunkModel).where(
            ContentChunkModel.tenant_id == tenant_id,
            ContentChunkModel.project_id == project_id,
        )
        if website_ids:
            statement = statement.where(ContentChunkModel.website_id.in_(website_ids))
        return list(self.session.scalars(statement.order_by(ContentChunkModel.chunk_index)))

    def to_schema(self, model: ContentChunkModel, *, url: str, title: str | None) -> ContentChunk:
        return ContentChunk(
            id=model.id,
            tenant_id=model.tenant_id,
            project_id=model.project_id,
            website_id=model.website_id,
            page_id=model.page_id,
            url=url,
            title=title,
            heading_path=model.heading_path,
            chunk_index=model.chunk_index,
            text=model.content,
            char_count=model.character_count,
        )
