from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, new_uuid


class AuditRun(Base, TimestampMixin):
    __tablename__ = "seo_audit_runs"
    __table_args__ = (Index("ix_audit_runs_tenant_project", "tenant_id", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    website_id: Mapped[str] = mapped_column(ForeignKey("websites.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    pages_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AuditFinding(Base):
    __tablename__ = "seo_audit_findings"
    __table_args__ = (
        Index("ix_audit_findings_tenant_run", "tenant_id", "audit_run_id"),
        Index("ix_audit_findings_page", "tenant_id", "page_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    website_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    audit_run_id: Mapped[str] = mapped_column(ForeignKey("seo_audit_runs.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    affected_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(nullable=False)
