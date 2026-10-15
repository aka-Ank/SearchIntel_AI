# mypy: disable-error-code=untyped-decorator

from celery import Celery
from celery.signals import worker_ready

from app.core.config import get_settings
from app.models import audit, crawl_job, page, project, tenant, website  # noqa: F401

settings = get_settings()
celery_app = Celery("searchintel", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_routes={
        "searchintel.execute_crawl": {"queue": "crawls"},
        "searchintel.execute_audit": {"queue": "audits"},
        "searchintel.recover_stale_jobs": {"queue": "crawls"},
    },
)


@celery_app.task(
    name="searchintel.execute_crawl",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def execute_crawl(_task: object, job_id: str) -> None:
    import asyncio

    from app.services.container import ServiceContainer

    container = ServiceContainer()
    asyncio.run(container.crawling.execute_job(job_id))


@celery_app.task(
    name="searchintel.execute_audit",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def execute_audit(_task: object, audit_id: str) -> None:
    import asyncio

    from app.services.container import ServiceContainer

    container = ServiceContainer()
    try:
        asyncio.run(container.seo_audits.execute_audit(audit_id))
    except Exception:
        from app.db.session import SessionLocal
        from app.models.audit import AuditRun

        with SessionLocal() as session:
            run = session.get(AuditRun, audit_id)
            if run is not None and run.status == "RUNNING":
                run.status = "PENDING"
                session.commit()
        raise


@celery_app.task(name="searchintel.recover_stale_jobs")
def recover_stale_jobs() -> None:
    from datetime import timedelta

    from app.db.session import SessionLocal
    from app.models.audit import AuditRun
    from app.models.common import utc_now
    from app.models.crawl_job import CrawlJob

    now = utc_now()
    with SessionLocal() as session:
        crawl_jobs = list(
            session.query(CrawlJob).filter(CrawlJob.status.in_(["PENDING", "RUNNING"]))
        )
        audit_runs = list(
            session.query(AuditRun).filter(AuditRun.status.in_(["PENDING", "RUNNING"]))
        )
        crawl_ids = [
            job.id
            for job in crawl_jobs
            if job.status == "PENDING"
            or not job.last_heartbeat_at
            or now - job.last_heartbeat_at > timedelta(minutes=15)
        ]
        audit_ids = [
            run.id
            for run in audit_runs
            if run.status == "PENDING"
            or not run.started_at
            or now - run.started_at > timedelta(minutes=15)
        ]
        for job in crawl_jobs:
            if job.id in crawl_ids and job.status == "RUNNING":
                job.status = "PENDING"
        for run in audit_runs:
            if run.id in audit_ids and run.status == "RUNNING":
                run.status = "PENDING"
        session.commit()
    for job_id in crawl_ids:
        celery_app.send_task("searchintel.execute_crawl", args=[job_id])
    for audit_id in audit_ids:
        celery_app.send_task("searchintel.execute_audit", args=[audit_id])


@worker_ready.connect
def recover_jobs_on_worker_start(**_kwargs: object) -> None:
    recover_stale_jobs.delay()
