from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, new_uuid, utc_now

if TYPE_CHECKING:
    from app.models.website import Website


class Page(Base, TimestampMixin):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("website_id", "normalized_url", name="uq_pages_website_normalized_url"),
        Index("ix_pages_tenant_project", "tenant_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    website_id: Mapped[str] = mapped_column(ForeignKey("websites.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    crawled_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    website: Mapped[Website] = relationship(back_populates="pages")
    chunks: Mapped[list[ContentChunk]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )


class ContentChunk(Base):
    __tablename__ = "content_chunks"
    __table_args__ = (
        Index("ix_chunks_tenant_project", "tenant_id", "project_id"),
        Index("ix_chunks_page_id", "page_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    website_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    page: Mapped[Page] = relationship(back_populates="chunks")
