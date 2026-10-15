import pytest

from app.core.url_security import UnsafeUrlError, UrlSafetyPolicy, validate_crawl_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://100.100.100.200/",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ],
)
def test_validate_crawl_url_blocks_internal_and_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_crawl_url(url)


def test_validate_crawl_url_normalizes_safe_public_url() -> None:
    assert validate_crawl_url("HTTPS://Example.com/path#section") == "https://example.com/path"


def test_explicit_local_permission_still_blocks_metadata_addresses() -> None:
    policy = UrlSafetyPolicy(allow_local_urls=True)
    with pytest.raises(UnsafeUrlError):
        validate_crawl_url("http://169.254.169.254/latest/meta-data", policy)
    with pytest.raises(UnsafeUrlError):
        validate_crawl_url("http://[::ffff:169.254.169.254]/", policy)
