from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CrawlJobStatus, new_uuid

if TYPE_CHECKING:
    from app.models.website import Website


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("ix_crawl_jobs_tenant_project", "tenant_id", "project_id"),
        Index(
            "uq_crawl_jobs_active_website",
            "tenant_id",
            "project_id",
            "website_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'RUNNING', 'CANCEL_REQUESTED')"),
            postgresql_where=text("status IN ('PENDING', 'RUNNING', 'CANCEL_REQUESTED')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    website_id: Mapped[str] = mapped_column(ForeignKey("websites.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default=CrawlJobStatus.pending.value,
        nullable=False,
    )
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_queued: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crawl_options: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    worker_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    website: Mapped[Website] = relationship(back_populates="crawl_jobs")
