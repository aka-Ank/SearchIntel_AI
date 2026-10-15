from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=1, max_length=200)
    website_url: str | None = None
    competitor_urls: list[str] = Field(default_factory=list)


class ProjectRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    website_url: str | None = None
    competitor_urls: list[str] = Field(default_factory=list)
