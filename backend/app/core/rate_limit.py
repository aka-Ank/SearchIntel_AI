from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from fastapi import Request

from app.core.config import get_settings

_RESOURCE_ROUTE = re.compile(r"^/api/v1/websites/[a-zA-Z0-9-]+/(crawl|seo-audits)$")


@dataclass(frozen=True)
class RateLimitRule:
    bucket: str
    limit: int
    window_seconds: int
    resource: str


def rate_limit_rule(request: Request) -> RateLimitRule | None:
    if request.method != "POST":
        return None
    settings = get_settings()
    path = request.url.path
    if path.endswith("/auth/login"):
        return RateLimitRule(
            "auth-login",
            settings.auth_login_rate_limit,
            settings.auth_login_rate_window_seconds,
            "auth-login",
        )
    if path.endswith("/auth/register"):
        return RateLimitRule(
            "auth-register",
            settings.auth_register_rate_limit,
            settings.auth_register_rate_window_seconds,
            "auth-register",
        )
    match = _RESOURCE_ROUTE.fullmatch(path)
    if match and match.group(1) == "crawl":
        return RateLimitRule(
            "crawl-enqueue",
            settings.crawl_enqueue_rate_limit,
            settings.crawl_enqueue_rate_window_seconds,
            "crawl-enqueue",
        )
    if match and match.group(1) == "seo-audits":
        return RateLimitRule(
            "audit-enqueue",
            settings.audit_enqueue_rate_limit,
            settings.audit_enqueue_rate_window_seconds,
            "audit-enqueue",
        )
    return None


def rate_limit_key(*, bucket: str, resource: str, client_host: str) -> str:
    identity = hashlib.sha256(f"{client_host}|{resource}".encode()).hexdigest()
    return f"searchintel:rate-limit:{bucket}:{identity}"
