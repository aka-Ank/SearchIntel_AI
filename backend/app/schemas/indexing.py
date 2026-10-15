from pydantic import BaseModel, Field


class IndexUrlRequest(BaseModel):
    tenant_id: str
    project_id: str
    website_id: str = "primary"
    url: str
    html: str | None = Field(default=None, description="Optional HTML fixture for local tests.")


class IndexUrlResponse(BaseModel):
    page_id: str
    url: str
    title: str | None
    chunk_count: int
