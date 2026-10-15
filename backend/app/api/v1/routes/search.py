from fastapi import APIRouter

from app.schemas.retrieval import SearchRequest, SearchResponse
from app.services.container import get_container

router = APIRouter()


@router.post("", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    return get_container().retrieval.search(
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        query=payload.query,
        strategy=payload.strategy,
        top_k=payload.top_k,
        website_ids=payload.website_ids,
        include_debug=payload.include_debug,
    )
