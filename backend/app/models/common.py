from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class WebsiteType(StrEnum):
    own = "OWN"
    competitor = "COMPETITOR"


class CrawlJobStatus(StrEnum):
    pending = "PENDING"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    cancel_requested = "CANCEL_REQUESTED"
    canceled = "CANCELED"


def new_uuid() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
