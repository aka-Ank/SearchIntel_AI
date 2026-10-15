from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser, require_tenant_role
from app.core.url_security import UnsafeUrlError
from app.schemas.crawl import CrawlJobRead, CrawlRequest
from app.services.container import get_container

router = APIRouter()


@router.get("/websites/{website_id}/crawl-jobs", response_model=list[CrawlJobRead])
def list_website_crawl_jobs(
    website_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> list[CrawlJobRead]:
    require_tenant_role(user=user, tenant_id=tenant_id)
    jobs = get_container().crawling.list_jobs(tenant_id=tenant_id, website_id=website_id)
    if jobs is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return jobs


@router.post("/websites/{website_id}/crawl", response_model=CrawlJobRead, status_code=202)
async def crawl_website(website_id: str, payload: CrawlRequest, user: CurrentUser) -> CrawlJobRead:
    require_tenant_role(user=user, tenant_id=payload.tenant_id, minimum_role="editor")
    try:
        job = await get_container().crawling.enqueue_crawl(
            tenant_id=payload.tenant_id,
            website_id=website_id,
            max_pages=payload.max_pages,
            max_depth=payload.max_depth,
            concurrency=payload.concurrency,
        )
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return job


@router.get("/crawl-jobs/{job_id}", response_model=CrawlJobRead)
def get_crawl_job(
    job_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> CrawlJobRead:
    require_tenant_role(user=user, tenant_id=tenant_id)
    job = get_container().crawling.get_job(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@router.delete("/crawl-jobs/{job_id}", response_model=CrawlJobRead)
def cancel_crawl_job(
    job_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> CrawlJobRead:
    require_tenant_role(user=user, tenant_id=tenant_id, minimum_role="editor")
    job = get_container().crawling.cancel_job(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job
