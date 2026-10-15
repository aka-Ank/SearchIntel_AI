from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpcore
import httpx

from app.core.url_security import UrlSafetyPolicy, resolve_crawl_addresses


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport that connects to validated DNS answers while retaining the URL host."""

    def __init__(self, safety_policy: UrlSafetyPolicy) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=PinnedNetworkBackend(safety_policy)
        )


class PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, safety_policy: UrlSafetyPolicy) -> None:
        self._safety_policy = safety_policy
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            addresses = await asyncio.to_thread(
                resolve_crawl_addresses, host, self._safety_policy
            )
        except ValueError as exc:
            raise httpcore.ConnectError("Crawler destination failed DNS safety validation") from exc

        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    str(address),
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("Crawler destination did not resolve to a usable address")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)
