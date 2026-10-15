from fastapi import APIRouter, HTTPException, Query

from app.core.url_security import UnsafeUrlError
from app.schemas.crawl import CrawlJobRead, CrawlRequest
from app.services.container import get_container

router = APIRouter()


@router.get("/websites/{website_id}/crawl-jobs", response_model=list[CrawlJobRead])
def list_website_crawl_jobs(website_id: str, tenant_id: str = Query(...)) -> list[CrawlJobRead]:
    jobs = get_container().crawling.list_jobs(tenant_id=tenant_id, website_id=website_id)
    if jobs is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return jobs


@router.post("/websites/{website_id}/crawl", response_model=CrawlJobRead, status_code=202)
async def crawl_website(website_id: str, payload: CrawlRequest) -> CrawlJobRead:
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
def get_crawl_job(job_id: str, tenant_id: str = Query(...)) -> CrawlJobRead:
    job = get_container().crawling.get_job(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@router.delete("/crawl-jobs/{job_id}", response_model=CrawlJobRead)
def cancel_crawl_job(job_id: str, tenant_id: str = Query(...)) -> CrawlJobRead:
    job = get_container().crawling.cancel_job(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job
