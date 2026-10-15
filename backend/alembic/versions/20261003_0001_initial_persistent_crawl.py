"""initial persistent crawl model

Revision ID: 20261003_0001
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261003_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_table(
        "websites",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("website_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_websites_tenant_project", "websites", ["tenant_id", "project_id"])
    op.create_table(
        "pages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("website_id", sa.String(length=36), sa.ForeignKey("websites.id"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pages_tenant_project", "pages", ["tenant_id", "project_id"])
    op.create_index(
        "uq_pages_website_normalized_url",
        "pages",
        ["website_id", "normalized_url"],
        unique=True,
    )
    op.create_table(
        "content_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("website_id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), sa.ForeignKey("pages.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chunks_tenant_project", "content_chunks", ["tenant_id", "project_id"])
    op.create_index("ix_chunks_page_id", "content_chunks", ["page_id"])
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("website_id", sa.String(length=36), sa.ForeignKey("websites.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("pages_discovered", sa.Integer(), nullable=False),
        sa.Column("pages_crawled", sa.Integer(), nullable=False),
        sa.Column("pages_failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_crawl_jobs_tenant_project", "crawl_jobs", ["tenant_id", "project_id"])


def downgrade() -> None:
    op.drop_table("crawl_jobs")
    op.drop_table("content_chunks")
    op.drop_table("pages")
    op.drop_table("websites")
    op.drop_table("projects")
    op.drop_table("tenants")
