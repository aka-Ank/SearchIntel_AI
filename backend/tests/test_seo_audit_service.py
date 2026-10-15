import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.url_security import UrlSafetyPolicy
from app.crawler.fetcher import FetchResponse
from app.models.audit import AuditRun
from app.models.common import WebsiteType
from app.models.page import Page
from app.repositories.projects import ProjectRepository
from app.repositories.websites import WebsiteRepository
from app.services.seo_audits import SeoAuditService


class AuditFetcher:
    user_agent = "SearchIntelTest"

    async def fetch_robots(self, _url: str, *, allowed_host: str | None = None) -> str:
        assert allowed_host == "example.test"
        return "User-agent: *\nDisallow: /private"

    async def fetch(self, url: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=404, content_type="text/html", text="not found")


@pytest.mark.anyio
async def test_audit_persists_findings_and_hides_other_tenants(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="A")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.test/",
            website_type=WebsiteType.own,
        )
        page = Page(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            url="https://example.test/private",
            normalized_url="https://example.test/private",
            title=None,
            meta_description=None,
            canonical_url=None,
            status_code=200,
            content_type="text/html",
            normalized_text="small content",
            content_hash="abc",
            word_count=2,
            audit_data={
                "meta_robots": [],
                "h1_count": 0,
                "heading_levels": [],
                "images": [],
                "internal_links": [],
                "external_links": [],
                "structured_data": [],
            },
        )
        run = AuditRun(tenant_id="tenant-a", project_id=project.id, website_id=website.id)
        session.add_all([page, run])
        session.commit()
        page_id, run_id = page.id, run.id
    service = SeoAuditService(
        session_factory=session_factory,
        fetcher=AuditFetcher(),
        safety_policy=UrlSafetyPolicy(allow_local_urls=True),
    )
    await service.execute_audit(run_id)
    status = service.get_run(tenant_id="tenant-a", audit_run_id=run_id)
    assert status and status.status == "COMPLETED" and status.pages_processed == 1
    findings = service.list_findings(tenant_id="tenant-a", audit_run_id=run_id)
    assert findings is not None
    assert {item.rule_id for item in findings} >= {
        "TITLE_MISSING",
        "ROBOTS_DISALLOW_OBSERVED",
        "INDEXABILITY_UNVERIFIED",
        "SITEMAP_MISSING",
    }
    page_findings = service.page_findings(tenant_id="tenant-a", page_id=page_id)
    assert page_findings and all(item.page_id == page_id for item in page_findings)
    assert service.get_run(tenant_id="tenant-b", audit_run_id=run_id) is None
    assert service.list_findings(tenant_id="tenant-b", audit_run_id=run_id) is None
    summary = service.summary(tenant_id="tenant-a", audit_run_id=run_id)
    assert summary and summary.total_findings == len(findings)
