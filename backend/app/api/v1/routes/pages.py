from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser, require_tenant_role
from app.schemas.pages import PageListItem, PageRead
from app.services.container import get_container

router = APIRouter()


@router.get("/projects/{project_id}/pages", response_model=list[PageListItem])
def list_pages(
    project_id: str,
    tenant_id: Annotated[str, Query()],
    user: CurrentUser,
    website_ids: Annotated[list[str] | None, Query()] = None,
) -> list[PageListItem]:
    require_tenant_role(user=user, tenant_id=tenant_id)
    return get_container().pages.list_pages(
        tenant_id=tenant_id,
        project_id=project_id,
        website_ids=website_ids,
    )


@router.get("/pages/{page_id}", response_model=PageRead)
def get_page(page_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser) -> PageRead:
    require_tenant_role(user=user, tenant_id=tenant_id)
    page = get_container().pages.get_page(tenant_id=tenant_id, page_id=page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
