from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.common import CrawlJobStatus, utc_now
from app.models.crawl_job import CrawlJob


class CrawlJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, tenant_id: str, project_id: str, website_id: str) -> CrawlJob:
        job = CrawlJob(
            tenant_id=tenant_id,
            project_id=project_id,
            website_id=website_id,
            status=CrawlJobStatus.pending.value,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_active(self, *, tenant_id: str, project_id: str, website_id: str) -> CrawlJob | None:
        return self.session.scalar(
            select(CrawlJob).where(
                CrawlJob.tenant_id == tenant_id,
                CrawlJob.project_id == project_id,
                CrawlJob.website_id == website_id,
                CrawlJob.status.in_(["PENDING", "RUNNING", "CANCEL_REQUESTED"]),
            )
        )

    def get(self, *, tenant_id: str, job_id: str) -> CrawlJob | None:
        return self.session.scalar(
            select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant_id)
        )

    def list_for_website(
        self, *, tenant_id: str, website_id: str, limit: int = 20
    ) -> list[CrawlJob]:
        return list(
            self.session.scalars(
                select(CrawlJob)
                .where(CrawlJob.tenant_id == tenant_id, CrawlJob.website_id == website_id)
                .order_by(
                    case(
                        (
                            CrawlJob.status.in_(["PENDING", "RUNNING", "CANCEL_REQUESTED"]),
                            0,
                        ),
                        else_=1,
                    ),
                    CrawlJob.started_at.desc(),
                )
                .limit(limit)
            )
        )

    def mark_running(self, job: CrawlJob) -> None:
        if job.status != CrawlJobStatus.pending.value:
            return
        job.status = CrawlJobStatus.running.value
        job.started_at = utc_now()
        self.session.flush()

    def update_progress(
        self,
        job: CrawlJob,
        *,
        discovered: int,
        queued: int,
        processed: int,
        crawled: int,
        failed: int,
    ) -> None:
        job.pages_discovered = discovered
        job.pages_queued = queued
        job.pages_processed = processed
        job.pages_crawled = crawled
        job.pages_failed = failed
        job.last_heartbeat_at = utc_now()
        self.session.flush()

    def request_cancel(self, job: CrawlJob) -> None:
        if job.status == "PENDING":
            self.mark_canceled(job)
        elif job.status == "RUNNING":
            job.status = "CANCEL_REQUESTED"
            self.session.flush()

    def mark_canceled(self, job: CrawlJob) -> None:
        job.status = "CANCELED"
        job.completed_at = utc_now()
        self.session.flush()

    def mark_completed(
        self,
        job: CrawlJob,
        *,
        pages_discovered: int,
        pages_crawled: int,
        pages_failed: int,
    ) -> None:
        job.status = CrawlJobStatus.completed.value
        job.pages_discovered = pages_discovered
        job.pages_crawled = pages_crawled
        job.pages_failed = pages_failed
        job.completed_at = utc_now()
        self.session.flush()

    def mark_failed(self, job: CrawlJob, *, error_message: str) -> None:
        job.status = CrawlJobStatus.failed.value
        job.error_message = error_message
        job.completed_at = utc_now()
        self.session.flush()
