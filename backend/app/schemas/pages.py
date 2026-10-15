from datetime import datetime

from pydantic import BaseModel


class PageListItem(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    website_id: str
    url: str
    normalized_url: str
    title: str | None
    content_hash: str
    word_count: int
    crawled_at: datetime


class PageRead(PageListItem):
    canonical_url: str | None
    meta_description: str | None
    status_code: int
    content_type: str
    normalized_text: str
