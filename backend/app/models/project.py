from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.website import Website


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="projects")
    websites: Mapped[list[Website]] = relationship(back_populates="project")
