from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.tenant import Tenant


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_tenant(self, tenant_id: str) -> Tenant:
        tenant = self.session.get(Tenant, tenant_id)
        if tenant is None:
            tenant = Tenant(id=tenant_id, name=tenant_id)
            self.session.add(tenant)
            self.session.flush()
        return tenant

    def create(self, *, tenant_id: str, name: str) -> Project:
        self.ensure_tenant(tenant_id)
        project = Project(tenant_id=tenant_id, name=name)
        self.session.add(project)
        self.session.flush()
        return project

    def get(self, *, tenant_id: str, project_id: str) -> Project | None:
        return self.session.scalar(
            select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        )

    def list_for_tenant(self, *, tenant_id: str) -> list[Project]:
        return list(self.session.scalars(select(Project).where(Project.tenant_id == tenant_id)))
