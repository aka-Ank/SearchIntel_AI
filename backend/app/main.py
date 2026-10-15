from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
