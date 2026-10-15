from fastapi import APIRouter

from app.auth import CurrentUser, require_tenant_role
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.container import get_container

router = APIRouter()


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(payload: RAGQueryRequest, user: CurrentUser) -> RAGQueryResponse:
    require_tenant_role(user=user, tenant_id=payload.tenant_id)
    return get_container().rag.query(
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        question=payload.question,
        search_strategy=payload.search_strategy,
        top_k=payload.top_k,
        website_ids=payload.website_ids,
        include_debug=payload.include_debug,
    )
