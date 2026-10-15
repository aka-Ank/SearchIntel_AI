from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_app_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


engine = create_app_engine()
SessionLocal = create_session_factory(engine)


def get_session() -> Generator[Session]:
    with SessionLocal() as session:
        yield session
