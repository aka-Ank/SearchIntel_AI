from types import SimpleNamespace

from app.crawler.parser import parse_html
from app.seo.engine import analyze_pages


def test_parser_captures_seo_signals_and_jsonld_edges() -> None:
    parsed = parse_html(
        "https://example.com/",
        """
    <html><head><title>Short</title><meta name="robots" content="noindex,follow">
    <script type="application/ld+json">{"@type":"Article"}</script></head>
    <body><h1>A</h1><h3>B</h3><img src="/x.png"><a href="/inside">i</a>
    <a href="https://other.test/">o</a></body></html>
    """,
    )
    assert parsed.audit_data["h1_count"] == 1
    assert parsed.audit_data["heading_levels"] == [1, 3]
    assert parsed.audit_data["meta_robots"] == ["noindex,follow"]
    assert parsed.audit_data["structured_data"] == [{"@type": "Article"}]
    assert parsed.audit_data["images"] == [{"src": "https://example.com/x.png", "alt": None}]
    assert parsed.audit_data["internal_links"] == ["https://example.com/inside"]


def test_seo_engine_reports_metadata_indexability_and_edge_cases() -> None:
    page = SimpleNamespace(
        id="p1",
        url="https://example.com/a",
        title=None,
        meta_description=None,
        canonical_url=None,
        status_code=404,
        word_count=3,
        content_hash="same",
        normalized_text="very short content",
        audit_data={
            "h1_count": 0,
            "heading_levels": [],
            "meta_robots": ["noindex"],
            "internal_links": [],
            "external_links": [],
            "images": [{"src": "/a.png", "alt": None}],
            "structured_data": [{"_invalid": True}],
        },
    )
    findings = analyze_pages([page])
    rules = {finding.rule_id for finding in findings}
    assert {
        "HTTP_NON_2XX",
        "TITLE_MISSING",
        "META_DESCRIPTION_MISSING",
        "H1_MISSING",
        "META_NOINDEX_OBSERVED",
        "INDEXABILITY_UNVERIFIED",
        "IMAGE_ALT_MISSING",
        "CONTENT_THIN",
        "STRUCTURED_DATA_INVALID",
    } <= rules
    unverified = next(item for item in findings if item.rule_id == "INDEXABILITY_UNVERIFIED")
    assert "cannot establish" in unverified.explanation


def test_duplicate_title_and_content_findings_are_deterministic() -> None:
    def page(url: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=url,
            url=url,
            title="A sufficiently long title for both pages",
            meta_description="A" * 100,
            canonical_url="https://example.com/",
            status_code=200,
            word_count=200,
            content_hash="samehash",
            normalized_text="word " * 200,
            audit_data={
                "h1_count": 1,
                "heading_levels": [1],
                "meta_robots": [],
                "internal_links": [],
                "external_links": [],
                "images": [],
                "structured_data": [],
            },
        )

    findings = analyze_pages([page("https://example.com/a"), page("https://example.com/b")])
    rules = [item.rule_id for item in findings]
    assert rules.count("TITLE_DUPLICATE") == 2
    assert rules.count("CONTENT_DUPLICATE") == 2
