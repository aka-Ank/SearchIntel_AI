from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.models.common import WebsiteType
from app.repositories.crawl_jobs import CrawlJobRepository
from app.repositories.projects import ProjectRepository
from app.repositories.websites import WebsiteRepository
from app.services.crawling import CrawlService


def test_worker_recovery_task_uses_a_consumed_queue() -> None:
    from app.tasks.queue import celery_app

    routes = celery_app.conf.task_routes
    assert routes["searchintel.recover_stale_jobs"]["queue"] == "crawls"


def test_celery_task_retries_transient_worker_failure(monkeypatch) -> None:
    from app.services import container as container_module
    from app.tasks.queue import celery_app

    attempts = 0

    class FakeCrawl:
        async def execute_job(self, job_id: str) -> None:
            nonlocal attempts
            assert job_id == "retry-probe"
            attempts += 1
            if attempts < 3:
                raise TimeoutError("transient worker failure")

    monkeypatch.setattr(
        container_module,
        "ServiceContainer",
        lambda: SimpleNamespace(crawling=FakeCrawl()),
    )
    task = celery_app.tasks["searchintel.execute_crawl"]
    result = task.apply(args=["retry-probe"])
    assert result.successful()
    assert attempts == 3


def test_worker_startup_recovery_requeues_stale_jobs_and_persists_state(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    from app.db import session as session_module
    from app.models.audit import AuditRun
    from app.models.common import utc_now
    from app.models.crawl_job import CrawlJob
    from app.tasks import queue

    now = utc_now()
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="A")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.test/",
            website_type=WebsiteType.own,
        )
        crawl = CrawlJob(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            status="RUNNING",
            pages_discovered=4,
            pages_processed=2,
            last_heartbeat_at=now - timedelta(minutes=30),
        )
        audit = AuditRun(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            status="RUNNING",
            pages_total=4,
            pages_processed=1,
            started_at=now - timedelta(minutes=30),
        )
        session.add_all([crawl, audit])
        session.commit()
        crawl_id, audit_id = crawl.id, audit.id

    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(session_module, "SessionLocal", session_factory)
    monkeypatch.setattr(
        queue.celery_app,
        "send_task",
        lambda name, args: dispatched.append((name, args[0])),
    )
    queue.recover_stale_jobs()

    assert set(dispatched) == {
        ("searchintel.execute_crawl", crawl_id),
        ("searchintel.execute_audit", audit_id),
    }
    with session_factory() as session:
        recovered_crawl = session.get(CrawlJob, crawl_id)
        recovered_audit = session.get(AuditRun, audit_id)
        assert recovered_crawl is not None and recovered_crawl.status == "PENDING"
        assert recovered_crawl.pages_processed == 2
        assert recovered_audit is not None and recovered_audit.status == "PENDING"
        assert recovered_audit.pages_processed == 1


def test_final_worker_failure_is_persisted_without_exception_details(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    from types import SimpleNamespace

    from app.db import session as session_module
    from app.models.crawl_job import CrawlJob
    from app.tasks.queue import persist_final_job_failure

    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="A")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.test/",
            website_type=WebsiteType.own,
        )
        job = CrawlJob(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            status="PENDING",
        )
        session.add(job)
        session.commit()
        job_id = job.id

    monkeypatch.setattr(session_module, "SessionLocal", session_factory)
    persist_final_job_failure(
        sender=SimpleNamespace(name="searchintel.execute_crawl"),
        args=(job_id,),
        exception=TimeoutError("secret query parameter must not be stored"),
    )
    with session_factory() as session:
        job = session.get(CrawlJob, job_id)
        assert job is not None and job.status == "FAILED"
        assert job.error_message == "Worker retries exhausted (TimeoutError)"


@pytest.mark.anyio
async def test_crawl_service_marks_transient_failure_retryable(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    from app.models.crawl_job import CrawlJob

    class FailingCrawler:
        async def crawl(self, **_kwargs: object) -> None:
            raise TimeoutError("private token should not be persisted")

    monkeypatch.setattr(
        "app.services.crawling.get_settings",
        lambda: SimpleNamespace(crawler_max_concurrency=2),
    )
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="A")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.test/",
            website_type=WebsiteType.own,
        )
        job = CrawlJob(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            status="PENDING",
            crawl_options={"max_pages": 2, "max_depth": 1, "concurrency": 1},
        )
        session.add(job)
        session.commit()
        job_id = job.id

    service = CrawlService(
        session_factory=session_factory, crawler=FailingCrawler(), indexing_service=None
    )  # type: ignore[arg-type]
    with pytest.raises(TimeoutError):
        await service.execute_job(job_id)
    with session_factory() as session:
        job = session.get(CrawlJob, job_id)
        assert job is not None and job.status == "PENDING"
        assert job.error_message == "Transient worker error: TimeoutError"


@pytest.mark.anyio
async def test_enqueue_deduplicates_and_job_access_is_tenant_scoped(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    import app.services.crawling as crawling_module

    monkeypatch.setattr(crawling_module, "_dispatch_task", lambda *_args: "task-1")
    monkeypatch.setattr(
        crawling_module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "allow_local_urls": True,
                "crawler_max_concurrency": 3,
            },
        )(),
    )
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="A")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.test/",
            website_type=WebsiteType.own,
        )
        session.commit()
        website_id = website.id
    service = CrawlService(session_factory=session_factory, crawler=None, indexing_service=None)  # type: ignore[arg-type]
    first = await service.enqueue_crawl(
        tenant_id="tenant-a", website_id=website_id, max_pages=10, max_depth=2, concurrency=20
    )
    second = await service.enqueue_crawl(
        tenant_id="tenant-a", website_id=website_id, max_pages=10, max_depth=2, concurrency=2
    )
    assert first and second and first.id == second.id
    assert first.status == "PENDING"
    assert service.get_job(tenant_id="tenant-b", job_id=first.id) is None
    canceled = service.cancel_job(tenant_id="tenant-a", job_id=first.id)
    assert canceled and canceled.status == "CANCELED"
    with session_factory() as session:
        job = CrawlJobRepository(session).get(tenant_id="tenant-a", job_id=first.id)
        assert job is not None and job.worker_task_id == "task-1"
        assert job.crawl_options["concurrency"] == 3
