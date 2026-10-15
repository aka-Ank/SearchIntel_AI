from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


class PageLike(Protocol):
    url: str
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    status_code: int
    word_count: int
    content_hash: str
    normalized_text: str
    audit_data: dict[str, object]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    affected_url: str
    explanation: str
    evidence: dict[str, object]
    recommended_action: str


def analyze_pages(
    pages: Sequence[PageLike], *, robots_disallowed: set[str] | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    title_counts = Counter(page.title.strip().casefold() for page in pages if page.title)
    description_counts = Counter(
        page.meta_description.strip().casefold() for page in pages if page.meta_description
    )
    hashes = Counter(page.content_hash for page in pages)
    for page in pages:
        url = page.url
        data = page.audit_data

        def add(
            rule: str,
            severity: str,
            explanation: str,
            evidence: dict[str, object],
            action: str,
            page_url: str = url,
        ) -> None:
            findings.append(Finding(rule, severity, page_url, explanation, evidence, action))

        if page.status_code < 200 or page.status_code >= 300:
            add(
                "HTTP_NON_2XX",
                "error" if page.status_code >= 400 else "warning",
                "The crawl observed a non-success HTTP response.",
                {"status_code": page.status_code},
                "Restore a successful response or update internal references to this URL.",
            )
        if not page.title:
            add(
                "TITLE_MISSING",
                "warning",
                "The page has no parsed title element.",
                {},
                "Add a concise, page-specific title element.",
            )
        else:
            title_length = len(page.title)
            if title_length < 30 or title_length > 60:
                add(
                    "TITLE_LENGTH",
                    "warning",
                    "The title is outside the configured 30–60 character guidance.",
                    {"length": title_length, "title": page.title},
                    "Rewrite the title to describe the page clearly and concisely.",
                )
            if title_counts[page.title.strip().casefold()] > 1:
                add(
                    "TITLE_DUPLICATE",
                    "warning",
                    "This title is shared by multiple crawled pages.",
                    {"title": page.title, "count": title_counts[page.title.strip().casefold()]},
                    "Give each page a distinct title that reflects its content.",
                )
        if not page.meta_description:
            add(
                "META_DESCRIPTION_MISSING",
                "warning",
                "The page has no parsed meta description.",
                {},
                "Add a unique summary of the page in a meta description.",
            )
        else:
            length = len(page.meta_description)
            if length < 70 or length > 160:
                add(
                    "META_DESCRIPTION_LENGTH",
                    "warning",
                    "The description is outside the configured 70–160 character guidance.",
                    {"length": length},
                    "Write a useful summary within the recommended length range.",
                )
            if description_counts[page.meta_description.strip().casefold()] > 1:
                add(
                    "META_DESCRIPTION_DUPLICATE",
                    "warning",
                    "This description is shared by multiple crawled pages.",
                    {"count": description_counts[page.meta_description.strip().casefold()]},
                    "Write a page-specific description.",
                )
        h1_count = _int(data, "h1_count")
        if h1_count == 0:
            add(
                "H1_MISSING",
                "warning",
                "No H1 heading was found in the fetched HTML.",
                {},
                "Add a descriptive primary heading.",
            )
        elif h1_count > 1:
            add(
                "H1_MULTIPLE",
                "warning",
                "Multiple H1 headings were found.",
                {"count": h1_count},
                "Use a clear primary H1, and make section headings subordinate.",
            )
        levels = [int(level) for level in _list(data, "heading_levels") if isinstance(level, int)]
        for previous, current in zip(levels, levels[1:], strict=False):
            if current > previous + 1:
                add(
                    "HEADING_HIERARCHY",
                    "warning",
                    "Heading levels skip one or more ranks.",
                    {"previous_level": previous, "next_level": current},
                    "Use heading levels in a logical nested sequence.",
                )
                break
        if not page.canonical_url:
            add(
                "CANONICAL_MISSING",
                "info",
                "No canonical link was observed in the fetched HTML.",
                {},
                "Set a canonical URL when this page has equivalent or duplicate URL variants.",
            )
        else:
            add(
                "CANONICAL_OBSERVED",
                "info",
                "A canonical URL was observed; this does not verify that search engines accept it.",
                {"canonical_url": page.canonical_url},
                "Confirm the canonical points to the preferred accessible URL.",
            )
            canonical = urlparse(page.canonical_url)
            page_url = urlparse(url)
            if canonical.scheme not in {"http", "https"} or not canonical.hostname:
                add(
                    "CANONICAL_INVALID",
                    "warning",
                    "The observed canonical is not a valid HTTP(S) URL.",
                    {"canonical_url": page.canonical_url},
                    "Set the canonical to an absolute HTTP(S) URL.",
                )
            elif canonical.hostname.casefold() != (page_url.hostname or "").casefold():
                add(
                    "CANONICAL_CROSS_DOMAIN",
                    "warning",
                    "The canonical points to another hostname; cross-domain canonicals should "
                    "be intentional.",
                    {"canonical_url": page.canonical_url, "page_hostname": page_url.hostname},
                    "Confirm the cross-domain canonical is deliberate and points to equivalent "
                    "content.",
                )
        robots = [str(value).lower() for value in _list(data, "meta_robots")]
        x_robots = data.get("x_robots_tag")
        if isinstance(x_robots, str) and "noindex" in x_robots.lower():
            robots.append(x_robots.lower())
        if any("noindex" in value for value in robots):
            add(
                "META_NOINDEX_OBSERVED",
                "warning",
                "A noindex directive was observed in page metadata.",
                {"meta_robots": robots},
                "Remove noindex only if this page is intended to be eligible for indexing.",
            )
        if robots_disallowed and url in robots_disallowed:
            add(
                "ROBOTS_DISALLOW_OBSERVED",
                "warning",
                "The URL is disallowed by the fetched robots.txt rules for this crawler.",
                {"url": url},
                "Review robots.txt if crawling or indexing this URL is intended.",
            )
        add(
            "INDEXABILITY_UNVERIFIED",
            "info",
            "HTML signals alone cannot establish that a search engine can or will index this page.",
            {"observed_meta_robots": robots, "http_status": page.status_code},
            "Verify robots access, canonical selection, rendering, and indexing in the relevant "
            "search console.",
        )
        internal = _list(data, "internal_links")
        external = _list(data, "external_links")
        add(
            "LINK_COUNTS",
            "info",
            "Links parsed from the fetched HTML; destinations not crawled were not verified.",
            {
                "internal": len(internal) if isinstance(internal, list) else 0,
                "external": len(external) if isinstance(external, list) else 0,
            },
            "Review important links and verify their destinations separately.",
        )
        images = _list(data, "images")
        missing_alt = [
            image
            for image in images
            if isinstance(image, dict) and not str(image.get("alt") or "").strip()
        ]
        if missing_alt:
            add(
                "IMAGE_ALT_MISSING",
                "warning",
                "Images without non-empty alt text were found.",
                {"count": len(missing_alt), "examples": missing_alt[:5]},
                "Add concise alt text for informative images; use empty alt for decorative images.",
            )
        if page.word_count < 100:
            add(
                "CONTENT_THIN",
                "warning",
                "The extracted page contains fewer than 100 words.",
                {"word_count": page.word_count},
                "Review whether the page needs more useful, original content.",
            )
        if hashes[page.content_hash] > 1:
            add(
                "CONTENT_DUPLICATE",
                "warning",
                "The exact extracted content hash appears on multiple crawled pages.",
                {"content_hash": page.content_hash, "count": hashes[page.content_hash]},
                "Consolidate duplicate pages or make their content meaningfully distinct.",
            )
        structured = _list(data, "structured_data")
        invalid = [item for item in structured if isinstance(item, dict) and item.get("_invalid")]
        if not structured:
            add(
                "STRUCTURED_DATA_MISSING",
                "info",
                "No JSON-LD structured data was observed.",
                {},
                "Add structured data only when it accurately describes the page.",
            )
        elif invalid:
            add(
                "STRUCTURED_DATA_INVALID",
                "warning",
                "One or more JSON-LD blocks could not be parsed as JSON.",
                {"invalid_blocks": len(invalid)},
                "Fix the JSON syntax and validate the structured data vocabulary.",
            )
        else:
            add(
                "STRUCTURED_DATA_PRESENT",
                "info",
                "JSON-LD was parsed; vocabulary and search eligibility were not externally "
                "validated.",
                {"blocks": len(structured)},
                "Validate the markup with an authoritative structured-data testing tool.",
            )

    for left_index, left in enumerate(pages):
        left_words = set(left.normalized_text.lower().split())
        if len(left_words) < 30:
            continue
        for right in pages[left_index + 1 :]:
            if left.content_hash == right.content_hash:
                continue
            right_words = set(right.normalized_text.lower().split())
            if len(right_words) < 30:
                continue
            similarity = len(left_words & right_words) / len(left_words | right_words)
            if similarity >= 0.9:
                findings.append(
                    Finding(
                        "CONTENT_NEAR_DUPLICATE",
                        "warning",
                        left.url,
                        "This page is highly similar to another crawled page.",
                        {"other_url": right.url, "word_set_similarity": round(similarity, 4)},
                        "Review overlapping pages and consolidate or differentiate their content.",
                    )
                )
    return findings


def _list(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def _int(data: dict[str, object], key: str) -> int:
    value = data.get(key, 0)
    return value if isinstance(value, int) else 0
