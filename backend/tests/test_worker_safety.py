import asyncio
import socket

import httpx
import pytest

from app.core.url_security import UnsafeUrlError, UrlSafetyPolicy, validate_crawl_url
from app.crawler.fetcher import HttpxFetcher, ResponseTooLargeError
from app.crawler.site_crawler import WebsiteCrawler


def _dns_answer(address: str):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, 0, 0, 0) if family == socket.AF_INET6 else (address, 0)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)]


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
    fetcher = HttpxFetcher(user_agent="test", timeout_seconds=1, max_response_bytes=5)
    with pytest.raises(ResponseTooLargeError, match="5-byte crawl limit"):
        await fetcher.fetch("https://8.8.8.8/")


@pytest.mark.anyio
async def test_http_transport_connects_to_validated_ip_and_preserves_host(monkeypatch) -> None:
    captured: list[str] = []

    async def respond(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request = await reader.readuntil(b"\r\n\r\n")
        captured.append(request.decode("ascii"))
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 2\r\n"
            b"Connection: close\r\n\r\nok"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _dns_answer("127.0.0.1"))
    try:
        fetcher = HttpxFetcher(
            user_agent="test",
            timeout_seconds=2,
            safety_policy=UrlSafetyPolicy(allow_local_urls=True),
        )
        response = await fetcher.fetch_scoped(
            f"http://crawl.test:{port}/", allowed_host="crawl.test"
        )
        assert response.text == "ok"
        assert "Host: crawl.test:" in captured[0]
        assert "crawl.test" in response.url
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.anyio
async def test_transport_rejects_private_dns_answer_after_public_preflight(monkeypatch) -> None:
    calls = 0

    def changing_dns(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        address = "93.184.216.34" if calls <= 2 else "127.0.0.1"
        return _dns_answer(address)

    monkeypatch.setattr(socket, "getaddrinfo", changing_dns)

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    fetcher = HttpxFetcher(user_agent="test", timeout_seconds=1)
    url = "http://rebind.test/"
    assert validate_crawl_url(url) == url
    with pytest.raises(httpx.ConnectError, match="DNS safety validation"):
        await fetcher.fetch(url)


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
