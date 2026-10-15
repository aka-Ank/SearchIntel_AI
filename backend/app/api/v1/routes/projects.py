from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser, require_tenant_role
from app.core.url_security import UnsafeUrlError
from app.schemas.competitors import CompetitorCoverageResponse
from app.schemas.projects import ProjectCreate, ProjectRead
from app.schemas.websites import WebsiteCreate, WebsiteRead
from app.services.container import get_container

router = APIRouter()


@router.get("/{project_id}/competitors/coverage", response_model=CompetitorCoverageResponse)
def competitor_coverage(
    project_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> CompetitorCoverageResponse:
    require_tenant_role(user=user, tenant_id=tenant_id)
    report = get_container().competitors.compare(tenant_id=tenant_id, project_id=project_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return report


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, user: CurrentUser) -> ProjectRead:
    require_tenant_role(user=user, tenant_id=payload.tenant_id, minimum_role="editor")
    try:
        return get_container().projects.create_project(payload)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[ProjectRead])
def list_projects(tenant_id: Annotated[str, Query()], user: CurrentUser) -> list[ProjectRead]:
    require_tenant_role(user=user, tenant_id=tenant_id)
    return get_container().projects.list_projects(tenant_id=tenant_id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> ProjectRead:
    require_tenant_role(user=user, tenant_id=tenant_id)
    project = get_container().projects.get_project(tenant_id=tenant_id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/websites", response_model=WebsiteRead, status_code=201)
def create_website(project_id: str, payload: WebsiteCreate, user: CurrentUser) -> WebsiteRead:
    require_tenant_role(user=user, tenant_id=payload.tenant_id, minimum_role="editor")
    try:
        website = get_container().projects.create_website(project_id=project_id, payload=payload)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if website is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return website


@router.get("/{project_id}/websites", response_model=list[WebsiteRead])
def list_websites(
    project_id: str, tenant_id: Annotated[str, Query()], user: CurrentUser
) -> list[WebsiteRead]:
    require_tenant_role(user=user, tenant_id=tenant_id)
    websites = get_container().projects.list_websites(tenant_id=tenant_id, project_id=project_id)
    if websites is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return websites
