from datetime import datetime

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    tenant_id: str
    max_pages: int = Field(default=10, ge=1, le=500)
    max_depth: int = Field(default=2, ge=0, le=10)
    concurrency: int = Field(default=4, ge=1, le=20)


class CrawlJobRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    website_id: str
    status: str
    pages_discovered: int
    pages_queued: int = 0
    pages_processed: int = 0
    pages_crawled: int
    pages_failed: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
