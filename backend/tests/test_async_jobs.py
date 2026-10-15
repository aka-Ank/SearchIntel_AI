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
