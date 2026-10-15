"""Persist async crawl progress and SEO audit records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0002"
down_revision: str | Sequence[str] | None = "20261003_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pages") as batch:
        batch.add_column(sa.Column("audit_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table("crawl_jobs") as batch:
        batch.add_column(sa.Column("pages_queued", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("pages_processed", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("crawl_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("worker_task_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index(
            "uq_crawl_jobs_active_website", ["tenant_id", "project_id", "website_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('PENDING', 'RUNNING', 'CANCEL_REQUESTED')"),
            postgresql_where=sa.text("status IN ('PENDING', 'RUNNING', 'CANCEL_REQUESTED')"),
        )
    op.create_table(
        "seo_audit_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("website_id", sa.String(36), sa.ForeignKey("websites.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("pages_total", sa.Integer(), nullable=False),
        sa.Column("pages_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_runs_tenant_project", "seo_audit_runs", ["tenant_id", "project_id"])
    op.create_table(
        "seo_audit_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("website_id", sa.String(36), nullable=False),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("pages.id"), nullable=True),
        sa.Column("audit_run_id", sa.String(36), sa.ForeignKey("seo_audit_runs.id"), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("affected_url", sa.String(2048), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_findings_tenant_run", "seo_audit_findings", ["tenant_id", "audit_run_id"])
    op.create_index("ix_audit_findings_page", "seo_audit_findings", ["tenant_id", "page_id"])


def downgrade() -> None:
    op.drop_table("seo_audit_findings")
    op.drop_table("seo_audit_runs")
    with op.batch_alter_table("crawl_jobs") as batch:
        batch.drop_index("uq_crawl_jobs_active_website")
        batch.drop_column("last_heartbeat_at")
        batch.drop_column("worker_task_id")
        batch.drop_column("crawl_options")
        batch.drop_column("pages_processed")
        batch.drop_column("pages_queued")
    with op.batch_alter_table("pages") as batch:
        batch.drop_column("audit_data")
