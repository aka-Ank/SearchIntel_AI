from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    url: str
    title: str | None = None
    meta_description: str | None = None
    headings: list[str] = Field(default_factory=list)
    body_text: str
    internal_links: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    audit_data: dict[str, object] = Field(default_factory=dict)
    content_hash: str


class ContentChunk(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    website_id: str
    page_id: str
    url: str
    title: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    chunk_index: int
    text: str
    char_count: int
