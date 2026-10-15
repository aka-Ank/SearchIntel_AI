from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    crawl,
    health,
    indexing,
    pages,
    projects,
    rag,
    search,
    seo,
    tenants,
)

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(crawl.router, tags=["crawl"])
router.include_router(seo.router, tags=["seo-audits"])
router.include_router(pages.router, tags=["pages"])
router.include_router(indexing.router, prefix="/index", tags=["index"])
router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(rag.router, prefix="/rag", tags=["rag"])
