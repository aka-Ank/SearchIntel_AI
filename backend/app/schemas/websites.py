from enum import StrEnum

from pydantic import BaseModel


class WebsiteTypeRead(StrEnum):
    own = "OWN"
    competitor = "COMPETITOR"


class WebsiteCreate(BaseModel):
    tenant_id: str
    base_url: str
    website_type: WebsiteTypeRead = WebsiteTypeRead.own


class WebsiteRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    base_url: str
    domain: str
    website_type: WebsiteTypeRead
