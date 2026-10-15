from fastapi import APIRouter, HTTPException

from app.core.url_security import UnsafeUrlError
from app.schemas.indexing import IndexUrlRequest, IndexUrlResponse
from app.services.container import get_container

router = APIRouter()


@router.post("/url", response_model=IndexUrlResponse)
async def index_url(payload: IndexUrlRequest) -> IndexUrlResponse:
    try:
        return await get_container().indexing.index_url(
            tenant_id=payload.tenant_id,
            project_id=payload.project_id,
            website_id=payload.website_id,
            url=payload.url,
            html=payload.html,
        )
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
