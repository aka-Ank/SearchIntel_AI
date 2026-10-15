from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, WebsiteType, new_uuid

if TYPE_CHECKING:
    from app.models.crawl_job import CrawlJob
    from app.models.page import Page
    from app.models.project import Project


class Website(Base, TimestampMixin):
    __tablename__ = "websites"
    __table_args__ = (Index("ix_websites_tenant_project", "tenant_id", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    website_type: Mapped[str] = mapped_column(
        String(20),
        default=WebsiteType.own.value,
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="websites")
    pages: Mapped[list[Page]] = relationship(back_populates="website")
    crawl_jobs: Mapped[list[CrawlJob]] = relationship(back_populates="website")
