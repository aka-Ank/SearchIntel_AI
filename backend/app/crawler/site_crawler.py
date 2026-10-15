from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from app.core.url_security import UrlSafetyPolicy, validate_crawl_url
from app.crawler.fetcher import Fetcher, FetchResponse
from app.crawler.parser import parse_html


@dataclass(frozen=True)
class CrawlPageResult:
    fetched: FetchResponse
    normalized_url: str
    internal_links: list[str]


@dataclass(frozen=True)
class CrawlRunResult:
    pages: list[CrawlPageResult]
    discovered_count: int
    failed_count: int
    failures: dict[str, str] = field(default_factory=dict)
    canceled: bool = False


class WebsiteCrawler:
    def __init__(
        self,
        *,
        fetcher: Fetcher,
        safety_policy: UrlSafetyPolicy,
        request_delay_seconds: float = 0.0,
    ) -> None:
        self._fetcher = fetcher
        self._safety_policy = safety_policy
        self._request_delay_seconds = request_delay_seconds

    async def crawl(
        self,
        *,
        root_url: str,
        max_pages: int,
        max_depth: int,
        concurrency: int,
        progress_callback: Callable[[int, int, int, int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> CrawlRunResult:
        root = validate_crawl_url(root_url, self._safety_policy)
        root_domain = urlparse(root).hostname
        queue: deque[tuple[str, int]] = deque([(root, 0)])
        queued = {root}
        visited: set[str] = set()
        pages: list[CrawlPageResult] = []
        failures: dict[str, str] = {}
        semaphore = asyncio.Semaphore(concurrency)
        pacing_lock = asyncio.Lock()
        next_request_at = 0.0
        robot_parser = RobotFileParser()
        robot_fetch = getattr(self._fetcher, "fetch_robots", None)
        if robot_fetch is not None:
            robots_url = root.rstrip("/") + "/robots.txt"
            robot_text = await robot_fetch(robots_url)
            robot_parser.set_url(robots_url)
            robot_parser.parse(robot_text.splitlines())

        processed = 0
        crawled_count = 0

        async def fetch_one(url: str) -> CrawlPageResult | None:
            nonlocal next_request_at
            async with semaphore:
                try:
                    if self._request_delay_seconds:
                        async with pacing_lock:
                            wait = next_request_at - monotonic()
                            if wait > 0:
                                await asyncio.sleep(wait)
                            next_request_at = monotonic() + self._request_delay_seconds
                    scoped_fetch = getattr(self._fetcher, "fetch_scoped", None)
                    fetched = (
                        await scoped_fetch(url, allowed_host=root_domain)
                        if scoped_fetch is not None
                        else await self._fetcher.fetch(url)
                    )
                except Exception as exc:
                    failures[url] = str(exc)
                    return None
                if urlparse(fetched.url).hostname != root_domain:
                    failures[url] = "Redirect left the configured crawl domain"
                    return None
                if "html" not in fetched.content_type.lower():
                    return CrawlPageResult(fetched=fetched, normalized_url=url, internal_links=[])
                parsed = parse_html(fetched.url, fetched.text)
                internal_links: list[str] = []
                for link in parsed.internal_links:
                    if urlparse(link).hostname != root_domain:
                        continue
                    internal_links.append(validate_crawl_url(link, self._safety_policy))
                return CrawlPageResult(
                    fetched=fetched,
                    normalized_url=url,
                    internal_links=list(dict.fromkeys(internal_links)),
                )

        while queue and len(pages) < max_pages:
            if should_cancel is not None and should_cancel():
                return CrawlRunResult(pages, len(queued), len(failures), failures, True)
            batch: list[tuple[str, int]] = []
            while queue and len(batch) < concurrency and len(pages) + len(batch) < max_pages:
                url, depth = queue.popleft()
                if robot_fetch is not None and not robot_parser.can_fetch(
                    getattr(self._fetcher, "user_agent", "*"), url
                ):
                    visited.add(url)
                    failures[url] = "Blocked by robots.txt"
                    processed += 1
                    continue
                if url in visited:
                    continue
                visited.add(url)
                batch.append((url, depth))

            results = await asyncio.gather(*(fetch_one(url) for url, _depth in batch))
            for result, (_url, depth) in zip(results, batch, strict=True):
                processed += 1
                if result is None:
                    continue
                pages.append(result)
                crawled_count += 1
                if depth >= max_depth:
                    continue
                for link in result.internal_links:
                    if link in queued or link in visited:
                        continue
                    if urlparse(link).hostname != root_domain:
                        continue
                    queued.add(link)
                    queue.append((link, depth + 1))
            if progress_callback is not None:
                progress_callback(len(queued), len(queue), processed, crawled_count, len(failures))

        return CrawlRunResult(
            pages=pages,
            discovered_count=len(queued),
            failed_count=len(failures),
            failures=failures,
        )
