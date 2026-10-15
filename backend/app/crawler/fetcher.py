from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

from app.core.url_security import UnsafeUrlError, UrlSafetyPolicy, validate_crawl_url


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    content_type: str
    text: str
    headers: dict[str, str] = field(default_factory=dict)


class Fetcher(Protocol):
    async def fetch(self, url: str) -> FetchResponse:
        """Fetch a URL and return text content."""


class ResponseTooLargeError(ValueError):
    """Raised when a crawl response exceeds the configured byte limit."""


class HttpxFetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        max_response_bytes: int = 5_000_000,
        safety_policy: UrlSafetyPolicy | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._safety_policy = safety_policy or UrlSafetyPolicy()
        self.user_agent = user_agent

    async def fetch(self, url: str) -> FetchResponse:
        return await self.fetch_scoped(url, allowed_host=None)

    async def fetch_scoped(self, url: str, *, allowed_host: str | None) -> FetchResponse:
        safe_url = validate_crawl_url(url, self._safety_policy)
        if allowed_host and urlparse(safe_url).hostname != allowed_host:
            raise UnsafeUrlError("URL is outside the configured crawl domain")
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": self._user_agent},
        ) as client:
            current = safe_url
            for redirect in range(6):
                response = await self._retry_request(client, current)
                if response.is_redirect:
                    await response.aclose()
                    if redirect == 5:
                        raise UnsafeUrlError("Too many redirects")
                    target = response.headers.get("location")
                    if not target:
                        raise UnsafeUrlError("Redirect response has no location")
                    current = validate_crawl_url(urljoin(current, target), self._safety_policy)
                    if allowed_host and urlparse(current).hostname != allowed_host:
                        raise UnsafeUrlError(
                            "Redirect target is outside the configured crawl domain"
                        )
                    continue
                try:
                    body = await self._read_limited(response)
                finally:
                    await response.aclose()
                return FetchResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    text=body,
                    headers=dict(response.headers),
                )
        raise UnsafeUrlError("Redirect handling failed")

    async def fetch_robots(self, url: str, *, allowed_host: str | None = None) -> str:
        safe_url = validate_crawl_url(url, self._safety_policy)
        if allowed_host and urlparse(safe_url).hostname != allowed_host:
            raise UnsafeUrlError("Robots URL is outside the configured crawl domain")
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": self._user_agent},
        ) as client:
            current = safe_url
            for redirect in range(6):
                response = await self._retry_request(client, current)
                if response.is_redirect:
                    await response.aclose()
                    if redirect == 5:
                        raise UnsafeUrlError("Too many robots.txt redirects")
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeUrlError("Robots redirect has no location")
                    current = validate_crawl_url(urljoin(current, location), self._safety_policy)
                    if allowed_host and urlparse(current).hostname != allowed_host:
                        raise UnsafeUrlError(
                            "Robots redirect is outside the configured crawl domain"
                        )
                    continue
                if response.status_code == 404:
                    await response.aclose()
                    return ""
                if response.status_code >= 500:
                    await response.aclose()
                    response.raise_for_status()
                try:
                    return await self._read_limited(response)
                finally:
                    await response.aclose()
        raise UnsafeUrlError("Robots redirect handling failed")

    async def _retry_request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        for attempt in range(4):
            try:
                request = client.build_request("GET", url)
                response = await client.send(request, stream=True)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    return response
                if attempt == 3:
                    return response
                await response.aclose()
            except httpx.TransportError:
                if attempt == 3:
                    raise
            await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError("unreachable retry state")

    async def _read_limited(self, response: httpx.Response) -> str:
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self._max_response_bytes:
            raise ResponseTooLargeError(
                f"Response exceeds the {self._max_response_bytes}-byte crawl limit"
            )
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > self._max_response_bytes:
                raise ResponseTooLargeError(
                    f"Response exceeds the {self._max_response_bytes}-byte crawl limit"
                )
        return bytes(body).decode(response.encoding or "utf-8", errors="replace")


class StaticHtmlFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self._html_by_url = html_by_url

    async def fetch(self, url: str) -> FetchResponse:
        safe_url = validate_crawl_url(url, UrlSafetyPolicy(allow_local_urls=True))
        html = self._html_by_url[safe_url]
        return FetchResponse(url=safe_url, status_code=200, content_type="text/html", text=html)
