from typing import Any

from fastapi import APIRouter, Response
from redis import Redis
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check(response: Response) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.db.session import SessionLocal

    checks: dict[str, Any] = {"database": "unavailable", "redis": "unavailable", "workers": []}
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        settings = get_settings()
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            checks["redis"] = "ok" if client.ping() else "unavailable"
        finally:
            client.close()
        if checks["redis"] == "ok":
            from app.tasks.queue import celery_app

            workers = celery_app.control.inspect(timeout=1.0).ping() or {}
            checks["workers"] = sorted(workers)
    except Exception:
        pass

    ready = checks["database"] == "ok" and checks["redis"] == "ok" and bool(checks["workers"])
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not_ready", "checks": checks}
