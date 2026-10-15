from fastapi import APIRouter, HTTPException, Query

from app.core.url_security import UnsafeUrlError
from app.schemas.projects import ProjectCreate, ProjectRead
from app.schemas.websites import WebsiteCreate, WebsiteRead
from app.services.container import get_container

router = APIRouter()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate) -> ProjectRead:
    try:
        return get_container().projects.create_project(payload)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[ProjectRead])
def list_projects(tenant_id: str = Query(...)) -> list[ProjectRead]:
    return get_container().projects.list_projects(tenant_id=tenant_id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, tenant_id: str = Query(...)) -> ProjectRead:
    project = get_container().projects.get_project(tenant_id=tenant_id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/websites", response_model=WebsiteRead, status_code=201)
def create_website(project_id: str, payload: WebsiteCreate) -> WebsiteRead:
    try:
        website = get_container().projects.create_website(project_id=project_id, payload=payload)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if website is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return website


@router.get("/{project_id}/websites", response_model=list[WebsiteRead])
def list_websites(project_id: str, tenant_id: str = Query(...)) -> list[WebsiteRead]:
    websites = get_container().projects.list_websites(tenant_id=tenant_id, project_id=project_id)
    if websites is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return websites
