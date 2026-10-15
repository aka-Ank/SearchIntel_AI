from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.url_security import UrlSafetyPolicy, validate_crawl_url
from app.models.common import WebsiteType
from app.repositories.projects import ProjectRepository
from app.repositories.websites import WebsiteRepository
from app.schemas.projects import ProjectCreate, ProjectRead
from app.schemas.websites import WebsiteCreate, WebsiteRead, WebsiteTypeRead


class ProjectService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._safety_policy = UrlSafetyPolicy(allow_local_urls=get_settings().allow_local_urls)

    def create_project(self, payload: ProjectCreate) -> ProjectRead:
        with self._session_factory() as session:
            project_repo = ProjectRepository(session)
            website_repo = WebsiteRepository(session)
            project = project_repo.create(tenant_id=payload.tenant_id, name=payload.name)

            website_url: str | None = None
            if payload.website_url:
                website_url = validate_crawl_url(payload.website_url, self._safety_policy)
                website_repo.create(
                    tenant_id=payload.tenant_id,
                    project_id=project.id,
                    base_url=website_url,
                    website_type=WebsiteType.own,
                )

            competitor_urls = [
                validate_crawl_url(url, self._safety_policy) for url in payload.competitor_urls
            ]
            for url in competitor_urls:
                website_repo.create(
                    tenant_id=payload.tenant_id,
                    project_id=project.id,
                    base_url=url,
                    website_type=WebsiteType.competitor,
                )

            result = ProjectRead(
                id=project.id,
                tenant_id=project.tenant_id,
                name=project.name,
                website_url=website_url,
                competitor_urls=competitor_urls,
            )
            session.commit()
            return result

    def get_project(self, *, tenant_id: str, project_id: str) -> ProjectRead | None:
        with self._session_factory() as session:
            project = ProjectRepository(session).get(tenant_id=tenant_id, project_id=project_id)
            if project is None:
                return None
            websites = WebsiteRepository(session).list_for_project(
                tenant_id=tenant_id,
                project_id=project_id,
            )
            own = next((website for website in websites if website.website_type == "OWN"), None)
            competitors = [
                website.base_url for website in websites if website.website_type == "COMPETITOR"
            ]
            return ProjectRead(
                id=project.id,
                tenant_id=project.tenant_id,
                name=project.name,
                website_url=own.base_url if own else None,
                competitor_urls=competitors,
            )

    def list_projects(self, *, tenant_id: str) -> list[ProjectRead]:
        with self._session_factory() as session:
            project_repo = ProjectRepository(session)
            website_repo = WebsiteRepository(session)
            projects = project_repo.list_for_tenant(tenant_id=tenant_id)
            result: list[ProjectRead] = []
            for project in projects:
                websites = website_repo.list_for_project(tenant_id=tenant_id, project_id=project.id)
                own = next((website for website in websites if website.website_type == "OWN"), None)
                result.append(
                    ProjectRead(
                        id=project.id,
                        tenant_id=tenant_id,
                        name=project.name,
                        website_url=own.base_url if own else None,
                        competitor_urls=[
                            website.base_url
                            for website in websites
                            if website.website_type == "COMPETITOR"
                        ],
                    )
                )
            return result

    def list_websites(self, *, tenant_id: str, project_id: str) -> list[WebsiteRead] | None:
        with self._session_factory() as session:
            project = ProjectRepository(session).get(tenant_id=tenant_id, project_id=project_id)
            if project is None:
                return None
            websites = WebsiteRepository(session).list_for_project(
                tenant_id=tenant_id, project_id=project_id
            )
            return [
                WebsiteRead(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    project_id=item.project_id,
                    base_url=item.base_url,
                    domain=item.domain,
                    website_type=WebsiteTypeRead(item.website_type),
                )
                for item in websites
            ]

    def create_website(self, *, project_id: str, payload: WebsiteCreate) -> WebsiteRead | None:
        with self._session_factory() as session:
            project = ProjectRepository(session).get(
                tenant_id=payload.tenant_id,
                project_id=project_id,
            )
            if project is None:
                return None
            safe_url = validate_crawl_url(payload.base_url, self._safety_policy)
            website_type = WebsiteType(payload.website_type.value)
            website = WebsiteRepository(session).create(
                tenant_id=payload.tenant_id,
                project_id=project_id,
                base_url=safe_url,
                website_type=website_type,
            )
            result = WebsiteRead(
                id=website.id,
                tenant_id=website.tenant_id,
                project_id=website.project_id,
                base_url=website.base_url,
                domain=website.domain,
                website_type=WebsiteTypeRead(website.website_type),
            )
            session.commit()
            return result
