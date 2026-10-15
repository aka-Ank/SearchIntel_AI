from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.url_security import normalize_url
from app.models.common import WebsiteType
from app.models.website import Website


class WebsiteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        tenant_id: str,
        project_id: str,
        base_url: str,
        website_type: WebsiteType,
    ) -> Website:
        normalized = normalize_url(base_url)
        domain = urlparse(normalized).hostname or ""
        website = Website(
            tenant_id=tenant_id,
            project_id=project_id,
            base_url=normalized,
            domain=domain,
            website_type=website_type.value,
        )
        self.session.add(website)
        self.session.flush()
        return website

    def get(self, *, tenant_id: str, website_id: str) -> Website | None:
        return self.session.scalar(
            select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
        )

    def list_for_project(self, *, tenant_id: str, project_id: str) -> list[Website]:
        return list(
            self.session.scalars(
                select(Website).where(
                    Website.tenant_id == tenant_id,
                    Website.project_id == project_id,
                )
            )
        )
