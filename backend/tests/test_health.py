from fastapi import Response

from app.api.v1.routes import health


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _statement):
        return 1


class _Redis:
    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None


class _Inspector:
    def __init__(self, workers: dict[str, dict[str, str]]) -> None:
        self._workers = workers

    def ping(self) -> dict[str, dict[str, str]]:
        return self._workers


def _stub_dependencies(monkeypatch, workers: dict[str, dict[str, str]]) -> None:
    import app.core.config as config
    import app.db.session as db_session
    import app.tasks.queue as queue

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: type("SettingsStub", (), {"redis_url": "redis://localhost:6379/0"})(),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.health.Redis.from_url",
        lambda *_args, **_kwargs: _Redis(),
    )
    monkeypatch.setattr(
        queue.celery_app.control,
        "inspect",
        lambda timeout: _Inspector(workers),
    )


def test_readiness_requires_a_live_worker(monkeypatch) -> None:
    _stub_dependencies(monkeypatch, {})
    response = Response()

    result = health.readiness_check(response)

    assert response.status_code == 503
    assert result == {
        "status": "not_ready",
        "checks": {"database": "ok", "redis": "ok", "workers": []},
    }


def test_readiness_reports_database_broker_and_worker(monkeypatch) -> None:
    _stub_dependencies(monkeypatch, {"celery@worker-1": {"ok": "pong"}})
    response = Response()

    result = health.readiness_check(response)

    assert response.status_code == 200
    assert result == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "workers": ["celery@worker-1"],
        },
    }
