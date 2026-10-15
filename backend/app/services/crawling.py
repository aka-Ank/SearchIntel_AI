from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.crawler.site_crawler import WebsiteCrawler
from app.models.common import CrawlJobStatus
from app.models.crawl_job import CrawlJob
from app.repositories.crawl_jobs import CrawlJobRepository
from app.repositories.websites import WebsiteRepository
from app.schemas.crawl import CrawlJobRead
from app.services.indexing import IndexingService


class CrawlService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        crawler: WebsiteCrawler,
        indexing_service: IndexingService,
    ) -> None:
        self._session_factory = session_factory
        self._crawler = crawler
        self._indexing_service = indexing_service

    async def enqueue_crawl(
        self, *, tenant_id: str, website_id: str, max_pages: int, max_depth: int, concurrency: int
    ) -> CrawlJobRead | None:
        with self._session_factory() as session:
            website = WebsiteRepository(session).get(tenant_id=tenant_id, website_id=website_id)
            if website is None:
                return None
            from app.core.url_security import UrlSafetyPolicy, validate_crawl_url

            settings = get_settings()
            validate_crawl_url(
                website.base_url, UrlSafetyPolicy(allow_local_urls=settings.allow_local_urls)
            )
            repo = CrawlJobRepository(session)
            active = repo.get_active(
                tenant_id=tenant_id, project_id=website.project_id, website_id=website.id
            )
            if active:
                return _job_to_schema(active)
            job = repo.create(
                tenant_id=tenant_id, project_id=website.project_id, website_id=website.id
            )
            job.crawl_options = {
                "max_pages": max_pages,
                "max_depth": max_depth,
                "concurrency": min(concurrency, get_settings().crawler_max_concurrency),
            }
            session.commit()
            job_id = job.id
            result = _job_to_schema(job)
        try:
            task_id = await asyncio.to_thread(_dispatch_task, "searchintel.execute_crawl", job_id)
            with self._session_factory() as session:
                queued = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
                if queued is not None:
                    queued.worker_task_id = task_id
                    session.commit()
        except Exception as exc:
            with self._session_factory() as session:
                failed = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
                if failed is not None:
                    CrawlJobRepository(session).mark_failed(
                        failed, error_message=f"Queue unavailable: {exc}"
                    )
                    session.commit()
            raise RuntimeError("Crawl queue unavailable") from exc
        return result

    async def execute_job(self, job_id: str) -> None:
        with self._session_factory() as session:
            job = session.get(CrawlJob, job_id)
            if job is None or job.status not in {"PENDING", "RUNNING"}:
                return
            website = WebsiteRepository(session).get(
                tenant_id=job.tenant_id, website_id=job.website_id
            )
            if website is None:
                CrawlJobRepository(session).mark_failed(
                    job, error_message="Website no longer exists"
                )
                session.commit()
                return
            tenant_id, project_id, website_id, root_url = (
                job.tenant_id,
                job.project_id,
                job.website_id,
                website.base_url,
            )
            options = dict(job.crawl_options or {})
            CrawlJobRepository(session).mark_running(job)
            session.commit()

        def progress(
            discovered: int, queued: int, processed: int, crawled: int, failed: int
        ) -> None:
            with self._session_factory() as session:
                current = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
                if current is not None:
                    CrawlJobRepository(session).update_progress(
                        current,
                        discovered=discovered,
                        queued=queued,
                        processed=processed,
                        crawled=crawled,
                        failed=failed,
                    )
                    session.commit()

        def should_cancel() -> bool:
            with self._session_factory() as session:
                current = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
                return current is None or current.status == "CANCEL_REQUESTED"

        try:
            result = await self._crawler.crawl(
                root_url=root_url,
                max_pages=int(options.get("max_pages", 10)),
                max_depth=int(options.get("max_depth", 2)),
                concurrency=min(
                    int(options.get("concurrency", 4)), get_settings().crawler_max_concurrency
                ),
                progress_callback=progress,
                should_cancel=should_cancel,
            )
            indexed = 0
            index_failures = 0
            for page_result in result.pages:
                if should_cancel():
                    break
                try:
                    self._indexing_service.index_fetched_page(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        website_id=website_id,
                        fetched=page_result.fetched,
                        normalized_url=page_result.normalized_url,
                    )
                    indexed += 1
                except Exception:
                    index_failures += 1
                progress(
                    result.discovered_count,
                    max(0, result.discovered_count - indexed - index_failures),
                    indexed + index_failures,
                    indexed,
                    result.failed_count + index_failures,
                )
            with self._session_factory() as session:
                repo = CrawlJobRepository(session)
                current = repo.get(tenant_id=tenant_id, job_id=job_id)
                if current is not None:
                    if result.canceled or current.status == "CANCEL_REQUESTED":
                        repo.mark_canceled(current)
                    else:
                        repo.mark_completed(
                            current,
                            pages_discovered=result.discovered_count,
                            pages_crawled=indexed,
                            pages_failed=result.failed_count + index_failures,
                        )
                    session.commit()
        except Exception as exc:
            retryable = True
            with self._session_factory() as session:
                current = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
                if current is not None:
                    if current.status == "CANCEL_REQUESTED":
                        CrawlJobRepository(session).mark_canceled(current)
                        retryable = False
                    else:
                        current.status = CrawlJobStatus.pending.value
                        current.error_message = f"Transient worker error: {type(exc).__name__}"
                    session.commit()
            if retryable:
                raise

    def cancel_job(self, *, tenant_id: str, job_id: str) -> CrawlJobRead | None:
        with self._session_factory() as session:
            repo = CrawlJobRepository(session)
            job = repo.get(tenant_id=tenant_id, job_id=job_id)
            if job is None:
                return None
            repo.request_cancel(job)
            session.commit()
            return _job_to_schema(job)

    async def crawl_website(
        self,
        *,
        tenant_id: str,
        website_id: str,
        max_pages: int,
        max_depth: int,
        concurrency: int,
    ) -> CrawlJobRead | None:
        with self._session_factory() as session:
            website = WebsiteRepository(session).get(tenant_id=tenant_id, website_id=website_id)
            if website is None:
                return None
            repo = CrawlJobRepository(session)
            job = repo.create(
                tenant_id=tenant_id,
                project_id=website.project_id,
                website_id=website.id,
            )
            repo.mark_running(job)
            session.commit()
            job_id = job.id
            project_id = website.project_id
            base_url = website.base_url

        try:
            crawl_result = await self._crawler.crawl(
                root_url=base_url,
                max_pages=max_pages,
                max_depth=max_depth,
                concurrency=concurrency,
            )
            crawled = 0
            for page_result in crawl_result.pages:
                self._indexing_service.index_fetched_page(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    website_id=website_id,
                    fetched=page_result.fetched,
                    normalized_url=page_result.normalized_url,
                )
                crawled += 1

            with self._session_factory() as session:
                repo = CrawlJobRepository(session)
                completed_job = repo.get(tenant_id=tenant_id, job_id=job_id)
                if completed_job is None:
                    return None
                repo.mark_completed(
                    completed_job,
                    pages_discovered=crawl_result.discovered_count,
                    pages_crawled=crawled,
                    pages_failed=crawl_result.failed_count,
                )
                result = _job_to_schema(completed_job)
                session.commit()
                return result
        except Exception as exc:
            with self._session_factory() as session:
                repo = CrawlJobRepository(session)
                failed_job = repo.get(tenant_id=tenant_id, job_id=job_id)
                if failed_job is None:
                    return None
                repo.mark_failed(failed_job, error_message=str(exc))
                result = _job_to_schema(failed_job)
                session.commit()
                return result

    def get_job(self, *, tenant_id: str, job_id: str) -> CrawlJobRead | None:
        with self._session_factory() as session:
            job = CrawlJobRepository(session).get(tenant_id=tenant_id, job_id=job_id)
            return _job_to_schema(job) if job else None

    def list_jobs(self, *, tenant_id: str, website_id: str) -> list[CrawlJobRead] | None:
        with self._session_factory() as session:
            website = WebsiteRepository(session).get(tenant_id=tenant_id, website_id=website_id)
            if website is None:
                return None
            jobs = CrawlJobRepository(session).list_for_website(
                tenant_id=tenant_id, website_id=website_id
            )
            return [_job_to_schema(job) for job in jobs]


def _job_to_schema(job: CrawlJob) -> CrawlJobRead:
    status = job.status
    if isinstance(status, CrawlJobStatus):
        status = status.value
    return CrawlJobRead(
        id=job.id,
        tenant_id=job.tenant_id,
        project_id=job.project_id,
        website_id=job.website_id,
        status=status,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        pages_processed=job.pages_processed,
        pages_crawled=job.pages_crawled,
        pages_failed=job.pages_failed,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


def _dispatch_task(task_name: str, job_id: str) -> str:
    from app.tasks.queue import celery_app

    return str(celery_app.send_task(task_name, args=[job_id]).id)
