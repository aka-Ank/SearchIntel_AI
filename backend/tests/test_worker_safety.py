import asyncio

import httpx
import pytest

from app.core.url_security import UnsafeUrlError, UrlSafetyPolicy
from app.crawler.fetcher import HttpxFetcher, ResponseTooLargeError
from app.crawler.site_crawler import WebsiteCrawler


@pytest.mark.anyio
async def test_transient_http_responses_are_retried(monkeypatch) -> None:
    responses = [
        httpx.Response(503, request=httpx.Request("GET", "https://8.8.8.8/")),
        httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="ok",
            request=httpx.Request("GET", "https://8.8.8.8/"),
        ),
    ]

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def build_request(self, method, url):
            return httpx.Request(method, url)

        async def send(self, request, *, stream):
            assert stream is True
            return responses.pop(0)

    monkeypatch.setattr("app.crawler.fetcher.httpx.AsyncClient", lambda **_kwargs: Client())

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    response = await HttpxFetcher(user_agent="test", timeout_seconds=1).fetch("https://8.8.8.8/")
    assert response.status_code == 200
    assert not responses


@pytest.mark.anyio
async def test_scoped_fetch_blocks_redirect_to_private_network(monkeypatch) -> None:
    calls = 0

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def build_request(self, method, url):
            return httpx.Request(method, url)

        async def send(self, request, *, stream):
            assert stream is True
            nonlocal calls
            calls += 1
            return httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/admin"},
                request=request,
            )

    monkeypatch.setattr("app.crawler.fetcher.httpx.AsyncClient", lambda **_kwargs: Client())
    fetcher = HttpxFetcher(user_agent="test", timeout_seconds=1)
    with pytest.raises(UnsafeUrlError):
        await fetcher.fetch_scoped("https://8.8.8.8/", allowed_host="8.8.8.8")
    assert calls == 1


@pytest.mark.anyio
async def test_fetcher_stops_reading_response_after_configured_byte_limit(monkeypatch) -> None:
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def build_request(self, method, url):
            return httpx.Request(method, url)

        async def send(self, request, *, stream):
            assert stream is True
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"123456",
                request=request,
            )

    monkeypatch.setattr("app.crawler.fetcher.httpx.AsyncClient", lambda **_kwargs: Client())
    fetcher = HttpxFetcher(
        user_agent="test", timeout_seconds=1, max_response_bytes=5
    )
    with pytest.raises(ResponseTooLargeError, match="5-byte crawl limit"):
        await fetcher.fetch("https://8.8.8.8/")


@pytest.mark.anyio
async def test_crawler_reports_partial_failures_and_honors_cancellation() -> None:
    class PartialFetcher:
        async def fetch(self, url: str):
            if url.endswith("/broken"):
                raise httpx.ConnectError("temporary outage")
            from app.crawler.fetcher import FetchResponse

            return FetchResponse(url, 200, "text/html", '<a href="/broken">broken</a>')

    crawler = WebsiteCrawler(fetcher=PartialFetcher(), safety_policy=UrlSafetyPolicy())
    result = await crawler.crawl(
        root_url="https://8.8.8.8/", max_pages=5, max_depth=1, concurrency=2
    )
    assert len(result.pages) == 1
    assert result.failed_count == 1
    assert "https://8.8.8.8/broken" in result.failures

    canceled = await crawler.crawl(
        root_url="https://8.8.8.8/",
        max_pages=5,
        max_depth=1,
        concurrency=2,
        should_cancel=lambda: True,
    )
    assert canceled.canceled is True
    assert canceled.pages == []
