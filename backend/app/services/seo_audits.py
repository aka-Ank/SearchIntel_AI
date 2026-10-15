from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.url_security import UrlSafetyPolicy, normalize_url, validate_crawl_url
from app.crawler.fetcher import Fetcher
from app.models.audit import AuditFinding, AuditRun
from app.models.common import utc_now
from app.models.page import Page
from app.models.website import Website
from app.schemas.seo import AuditFindingRead, AuditRunRead, AuditSummaryRead
from app.services.crawling import _dispatch_task


class SeoAuditService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        fetcher: Fetcher,
        safety_policy: UrlSafetyPolicy,
    ) -> None:
        self._session_factory = session_factory
        self._fetcher = fetcher
        self._safety_policy = safety_policy

    async def enqueue(self, *, tenant_id: str, website_id: str) -> AuditRunRead | None:
        with self._session_factory() as session:
            website = session.scalar(
                select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
            )
            if website is None:
                return None
            run = AuditRun(
                tenant_id=tenant_id, project_id=website.project_id, website_id=website.id
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            result = _run_schema(run)
            run_id = run.id
        try:
            await asyncio.to_thread(_dispatch_task, "searchintel.execute_audit", run_id)
        except Exception as exc:
            with self._session_factory() as session:
                current = session.get(AuditRun, run_id)
                if current:
                    current.status = "FAILED"
                    current.error_message = f"Queue unavailable: {exc}"[:1000]
                    current.completed_at = utc_now()
                    session.commit()
            raise RuntimeError("Audit queue unavailable") from exc
        return result

    async def execute_audit(self, audit_run_id: str) -> None:
        with self._session_factory() as session:
            run = session.get(AuditRun, audit_run_id)
            if run is None or run.status != "PENDING":
                return
            website = session.scalar(
                select(Website).where(
                    Website.id == run.website_id, Website.tenant_id == run.tenant_id
                )
            )
            if website is None:
                run.status = "FAILED"
                run.error_message = "Website no longer exists"
                run.completed_at = utc_now()
                session.commit()
                return
            pages = list(
                session.scalars(
                    select(Page)
                    .where(
                        Page.tenant_id == run.tenant_id,
                        Page.project_id == run.project_id,
                        Page.website_id == run.website_id,
                    )
                    .order_by(Page.url)
                )
            )
            tenant_id, project_id, website_id = run.tenant_id, run.project_id, run.website_id
            base_url = website.base_url
            run.status = "RUNNING"
            run.pages_total = len(pages)
            run.started_at = utc_now()
            session.commit()

        from app.seo.engine import Finding, analyze_pages

        parsed_base = urlparse(base_url)
        host = parsed_base.hostname or ""
        robots_text = ""
        sitemap_exists = False
        sitemap_valid = False
        sitemap_locations: list[str] = []
        robots_fetch = getattr(self._fetcher, "fetch_robots", None)
        if robots_fetch:
            try:
                robots_text = await robots_fetch(
                    f"{parsed_base.scheme}://{parsed_base.netloc}/robots.txt", allowed_host=host
                )
            except Exception:
                robots_text = ""
        robots_lines = robots_text.splitlines()
        for line in robots_lines:
            if line.lower().startswith("sitemap:"):
                sitemap_locations.append(line.split(":", 1)[1].strip())
        candidates = sitemap_locations or [
            f"{parsed_base.scheme}://{parsed_base.netloc}/sitemap.xml"
        ]
        for sitemap_url in candidates[:5]:
            try:
                safe = validate_crawl_url(sitemap_url, self._safety_policy)
                if urlparse(safe).hostname != host:
                    continue
                scoped_fetch = getattr(self._fetcher, "fetch_scoped", None)
                response = (
                    await scoped_fetch(safe, allowed_host=host)
                    if scoped_fetch is not None
                    else await self._fetcher.fetch(safe)
                )
                sitemap_exists = 200 <= response.status_code < 300
                if sitemap_exists:
                    sitemap_root = ET.fromstring(response.text)
                    if not sitemap_root.tag.endswith(("urlset", "sitemapindex")):
                        continue
                    sitemap_valid = True
                    break
            except Exception:
                continue
        disallowed: set[str] = set()
        if robots_text:
            from urllib.robotparser import RobotFileParser

            parser = RobotFileParser()
            parser.set_url(f"{parsed_base.scheme}://{parsed_base.netloc}/robots.txt")
            parser.parse(robots_lines)
            for page in pages:
                if not parser.can_fetch(getattr(self._fetcher, "user_agent", "*"), page.url):
                    disallowed.add(page.url)

        findings = analyze_pages(pages, robots_disallowed=disallowed)
        page_by_url = {normalize_url(page.url): page for page in pages}
        for page in pages:
            raw_links = page.audit_data.get("internal_links", [])
            targets = raw_links if isinstance(raw_links, list) else []
            for target in targets:
                if not isinstance(target, str):
                    continue
                linked = page_by_url.get(normalize_url(target))
                if linked and linked.status_code >= 400:
                    findings.append(
                        Finding(
                            "BROKEN_INTERNAL_LINK",
                            "error",
                            page.url,
                            "A link points to a crawled page that returned an HTTP error.",
                            {"target_url": linked.url, "status_code": linked.status_code},
                            "Update the link or restore the destination page.",
                        )
                    )
        severity = "info" if not sitemap_exists else ("info" if sitemap_valid else "warning")
        findings.append(
            Finding(
                "SITEMAP_MISSING"
                if not sitemap_exists
                else ("SITEMAP_VALID" if sitemap_valid else "SITEMAP_INVALID"),
                severity,
                base_url,
                "No sitemap.xml or robots-declared sitemap returned valid XML."
                if not sitemap_valid
                else "A sitemap URL was fetched and parsed as XML; URL coverage was not verified.",
                {"robots_txt_observed": bool(robots_text), "sitemap_candidates": candidates[:5]},
                "Publish a valid sitemap and reference it in robots.txt when appropriate."
                if not sitemap_valid
                else "Check that sitemap URLs are canonical and return successful responses.",
            )
        )

        now = datetime.now(UTC)
        with self._session_factory() as session:
            run = session.get(AuditRun, audit_run_id)
            if run is None:
                return
            for finding in findings:
                page_model = page_by_url.get(normalize_url(finding.affected_url))
                session.add(
                    AuditFinding(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        website_id=website_id,
                        page_id=page_model.id if page_model else None,
                        audit_run_id=audit_run_id,
                        rule_id=finding.rule_id,
                        severity=finding.severity,
                        affected_url=finding.affected_url,
                        explanation=finding.explanation,
                        evidence=finding.evidence,
                        recommended_action=finding.recommended_action,
                        detected_at=now,
                    )
                )
            run.pages_processed = len(pages)
            run.status = "COMPLETED"
            run.completed_at = now
            session.commit()

    def get_run(self, *, tenant_id: str, audit_run_id: str) -> AuditRunRead | None:
        with self._session_factory() as session:
            run = session.scalar(
                select(AuditRun).where(AuditRun.id == audit_run_id, AuditRun.tenant_id == tenant_id)
            )
            return _run_schema(run) if run else None

    def list_runs(self, *, tenant_id: str, website_id: str) -> list[AuditRunRead] | None:
        with self._session_factory() as session:
            website = session.scalar(
                select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
            )
            if website is None:
                return None
            runs = session.scalars(
                select(AuditRun)
                .where(AuditRun.website_id == website_id, AuditRun.tenant_id == tenant_id)
                .order_by(AuditRun.created_at.desc())
                .limit(20)
            ).all()
            return [_run_schema(run) for run in runs]

    def list_findings(
        self,
        *,
        tenant_id: str,
        audit_run_id: str,
        severity: str | None = None,
        rule_id: str | None = None,
        page_id: str | None = None,
    ) -> list[AuditFindingRead] | None:
        with self._session_factory() as session:
            run = session.scalar(
                select(AuditRun).where(AuditRun.id == audit_run_id, AuditRun.tenant_id == tenant_id)
            )
            if run is None:
                return None
            query = select(AuditFinding).where(
                AuditFinding.audit_run_id == audit_run_id, AuditFinding.tenant_id == tenant_id
            )
            if severity:
                query = query.where(AuditFinding.severity == severity.lower())
            if rule_id:
                query = query.where(AuditFinding.rule_id == rule_id)
            if page_id:
                query = query.where(AuditFinding.page_id == page_id)
            rows = session.scalars(
                query.order_by(AuditFinding.severity, AuditFinding.rule_id)
            ).all()
            return [_finding_schema(row) for row in rows]

    def summary(self, *, tenant_id: str, audit_run_id: str) -> AuditSummaryRead | None:
        run = self.get_run(tenant_id=tenant_id, audit_run_id=audit_run_id)
        findings = self.list_findings(tenant_id=tenant_id, audit_run_id=audit_run_id)
        if run is None or findings is None:
            return None
        severities = Counter(item.severity for item in findings)
        rules = Counter(item.rule_id for item in findings)
        return AuditSummaryRead(
            audit_run=run,
            total_findings=len(findings),
            by_severity=dict(severities),
            by_rule=dict(rules),
        )

    def page_findings(self, *, tenant_id: str, page_id: str) -> list[AuditFindingRead] | None:
        with self._session_factory() as session:
            page = session.scalar(
                select(Page).where(Page.id == page_id, Page.tenant_id == tenant_id)
            )
            if page is None:
                return None
            findings = session.scalars(
                select(AuditFinding)
                .where(AuditFinding.page_id == page_id, AuditFinding.tenant_id == tenant_id)
                .order_by(AuditFinding.detected_at.desc())
            )
            return [_finding_schema(item) for item in findings]


def _run_schema(run: AuditRun) -> AuditRunRead:
    return AuditRunRead(
        id=run.id,
        tenant_id=run.tenant_id,
        project_id=run.project_id,
        website_id=run.website_id,
        status=run.status,
        pages_total=run.pages_total,
        pages_processed=run.pages_processed,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


def _finding_schema(item: AuditFinding) -> AuditFindingRead:
    return AuditFindingRead(
        id=item.id,
        tenant_id=item.tenant_id,
        project_id=item.project_id,
        website_id=item.website_id,
        page_id=item.page_id,
        audit_run_id=item.audit_run_id,
        rule_id=item.rule_id,
        severity=item.severity,
        affected_url=item.affected_url,
        explanation=item.explanation,
        evidence=item.evidence,
        recommended_action=item.recommended_action,
        detected_at=item.detected_at,
    )
