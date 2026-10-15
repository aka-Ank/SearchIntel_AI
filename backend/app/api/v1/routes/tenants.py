from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.auth import CurrentUser, require_tenant_role
from app.models.auth import TenantMembership, User
from app.models.common import new_uuid, utc_now
from app.models.tenant import Tenant
from app.schemas.auth import TenantCreate, TenantMemberCreate, TenantMemberRead, TenantRead
from app.services.container import get_container

router = APIRouter()


@router.get("", response_model=list[TenantRead])
def list_tenants(user: CurrentUser) -> list[TenantRead]:
    with get_container().session_factory() as session:
        rows = session.execute(
            select(Tenant, TenantMembership.role)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .where(TenantMembership.user_id == user.id)
            .order_by(Tenant.name)
        ).all()
        return [TenantRead(id=tenant.id, name=tenant.name, role=role) for tenant, role in rows]


@router.post("", response_model=TenantRead, status_code=201)
def create_tenant(payload: TenantCreate, user: CurrentUser) -> TenantRead:
    now = utc_now()
    tenant = Tenant(id=new_uuid(), name=payload.name, created_at=now, updated_at=now)
    membership = TenantMembership(
        id=new_uuid(),
        tenant_id=tenant.id,
        user_id=user.id,
        role="owner",
        created_at=now,
        updated_at=now,
    )
    with get_container().session_factory.begin() as session:
        # Flush the tenant first: the membership carries a database FK, but no
        # ORM relationship, so add_all alone does not define insert ordering.
        session.add(tenant)
        session.flush()
        session.add(membership)
    return TenantRead(id=tenant.id, name=tenant.name, role="owner")


@router.get("/{tenant_id}/members", response_model=list[TenantMemberRead])
def list_members(tenant_id: str, user: CurrentUser) -> list[TenantMemberRead]:
    require_tenant_role(user=user, tenant_id=tenant_id, minimum_role="admin")
    with get_container().session_factory() as session:
        rows = session.execute(
            select(User, TenantMembership.role)
            .join(TenantMembership, TenantMembership.user_id == User.id)
            .where(TenantMembership.tenant_id == tenant_id)
            .order_by(User.email)
        ).all()
        return [
            TenantMemberRead(user_id=member.id, email=member.email, role=role)
            for member, role in rows
        ]


@router.post("/{tenant_id}/members", response_model=TenantMemberRead, status_code=201)
def add_member(tenant_id: str, payload: TenantMemberCreate, user: CurrentUser) -> TenantMemberRead:
    require_tenant_role(user=user, tenant_id=tenant_id, minimum_role="admin")
    with get_container().session_factory.begin() as session:
        member = session.scalar(
            select(User).where(func.lower(User.email) == str(payload.email).lower())
        )
        if member is None:
            raise HTTPException(status_code=404, detail="User must register before being added")
        membership = session.scalar(
            select(TenantMembership).where(
                TenantMembership.user_id == member.id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        if membership is None:
            membership = TenantMembership(tenant_id=tenant_id, user_id=member.id, role=payload.role)
            session.add(membership)
        else:
            membership.role = payload.role
        return TenantMemberRead(user_id=member.id, email=member.email, role=payload.role)
