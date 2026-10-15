import pytest

from app.core.url_security import UnsafeUrlError, UrlSafetyPolicy
from app.crawler.fetcher import StaticHtmlFetcher
from app.crawler.site_crawler import WebsiteCrawler

SITE = {
    "https://example.com/": """
    <html><body>
      <a href="/about">About</a>
      <a href="/about#team">About duplicate</a>
      <a href="https://other.example/">External</a>
    </body></html>
    """,
    "https://example.com/about": """
    <html><body>
      <a href="/pricing">Pricing</a>
      <p>About page content.</p>
    </body></html>
    """,
    "https://example.com/pricing": "<html><body><p>Pricing content.</p></body></html>",
}


@pytest.mark.anyio
async def test_crawler_discovers_internal_links_and_ignores_external_domain() -> None:
    crawler = WebsiteCrawler(
        fetcher=StaticHtmlFetcher(SITE),
        safety_policy=UrlSafetyPolicy(allow_local_urls=False),
    )

    result = await crawler.crawl(
        root_url="https://example.com/",
        max_pages=10,
        max_depth=2,
        concurrency=2,
    )

    urls = [page.normalized_url for page in result.pages]
    assert urls == [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/pricing",
    ]
    assert "https://other.example/" not in urls
    assert result.discovered_count == 3


@pytest.mark.anyio
async def test_crawler_respects_max_pages_and_depth() -> None:
    crawler = WebsiteCrawler(
        fetcher=StaticHtmlFetcher(SITE),
        safety_policy=UrlSafetyPolicy(allow_local_urls=False),
    )

    max_pages_result = await crawler.crawl(
        root_url="https://example.com/",
        max_pages=1,
        max_depth=3,
        concurrency=2,
    )
    depth_result = await crawler.crawl(
        root_url="https://example.com/",
        max_pages=10,
        max_depth=1,
        concurrency=2,
    )

    assert [page.normalized_url for page in max_pages_result.pages] == ["https://example.com/"]
    assert [page.normalized_url for page in depth_result.pages] == [
        "https://example.com/",
        "https://example.com/about",
    ]


@pytest.mark.anyio
async def test_crawler_blocks_unsafe_root_url() -> None:
    crawler = WebsiteCrawler(
        fetcher=StaticHtmlFetcher({}),
        safety_policy=UrlSafetyPolicy(allow_local_urls=False),
    )

    with pytest.raises(UnsafeUrlError):
        await crawler.crawl(root_url="http://127.0.0.1", max_pages=1, max_depth=0, concurrency=1)
