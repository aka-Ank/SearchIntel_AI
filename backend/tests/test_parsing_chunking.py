from pathlib import Path

from app.crawler.parser import parse_html
from app.processing.chunking import StructureAwareChunker

FIXTURE = Path(__file__).parent / "fixtures" / "sample_page.html"


def test_parse_html_extracts_metadata_content_and_links() -> None:
    page = parse_html("https://example.com/javascript-seo", FIXTURE.read_text())

    assert page.title == "JavaScript SEO Guide"
    assert "rendering, crawling, indexing" in page.meta_description
    assert "JavaScript SEO Guide" in page.headings
    assert "window.secret" not in page.body_text
    assert "https://example.com/rendering" in page.internal_links
    assert "https://competitor.example/js-seo" in page.external_links
    assert page.canonical_url == "https://example.com/javascript-seo"


def test_chunker_creates_tenant_scoped_chunks() -> None:
    page = parse_html("https://example.com/javascript-seo", FIXTURE.read_text())
    chunks = StructureAwareChunker(target_chars=180).chunk_page(
        tenant_id="tenant-a",
        project_id="project-a",
        website_id="site-a",
        page_id="page-a",
        page=page,
    )

    assert chunks
    assert {chunk.tenant_id for chunk in chunks} == {"tenant-a"}
    assert {chunk.project_id for chunk in chunks} == {"project-a"}
    assert all(chunk.char_count == len(chunk.text) for chunk in chunks)
