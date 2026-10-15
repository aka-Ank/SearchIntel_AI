import hmac
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings


class CookieCsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        cookie_name = "searchintel_session"
        csrf_name = "searchintel_csrf"
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get(
            cookie_name
        ):
            cookie_token = request.cookies.get(csrf_name, "")
            header_token = request.headers.get("x-csrf-token", "")
            if (
                not cookie_token
                or not header_token
                or not hmac.compare_digest(cookie_token, header_token)
            ):
                return Response(status_code=403, content="CSRF validation failed")

        response = await call_next(request)
        set_cookies = response.headers.getlist("set-cookie")
        if (
            request.url.path.endswith("/auth/login")
            and response.status_code < 400
            and any(cookie_name in value for value in set_cookies)
        ):
            csrf_token = secrets.token_urlsafe(32)
            response.set_cookie(
                csrf_name,
                csrf_token,
                max_age=settings.auth_token_lifetime_seconds,
                path="/",
                secure=settings.secure_auth_cookies,
                httponly=False,
                samesite=settings.auth_cookie_samesite,
            )
        if request.url.path.endswith("/auth/logout") and response.status_code < 400:
            response.delete_cookie(csrf_name, path="/")
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(CookieCsrfMiddleware)
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
