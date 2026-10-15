from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import audit, auth, crawl_job, page, project, tenant, website  # noqa: F401


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    yield factory
    Base.metadata.drop_all(engine)


class InMemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)

    async def eval(self, _script: str, _numkeys: int, key: str, window: str) -> list[int]:
        count = int(self.values.get(key, "0")) + 1
        self.values[key] = str(count)
        self.ttls.setdefault(key, int(window))
        return [count, self.ttls[key]]


@pytest.fixture(autouse=True)
def fake_auth_session_store(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRedis()
    monkeypatch.setattr("app.auth._redis_client", lambda _url: store)
    monkeypatch.setattr("app.main._redis_client", lambda _url: store)
