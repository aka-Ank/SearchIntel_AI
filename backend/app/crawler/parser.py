from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.schemas.content import ParsedPage

WHITESPACE_RE = re.compile(r"\s+")
IGNORED_TAGS = {"script", "style", "noscript", "svg", "canvas"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "tr", "br"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _ContentParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title: str | None = None
        self.meta_description: str | None = None
        self.canonical_url: str | None = None
        self.meta_robots: list[str] = []
        self.heading_levels: list[int] = []
        self.h1_count = 0
        self.images: list[dict[str, object]] = []
        self.structured_data: list[dict[str, object]] = []
        self._jsonld = False
        self._jsonld_buffer: list[str] = []
        self.headings: list[str] = []
        self.links: list[str] = []
        self._text_parts: list[str] = []
        self._current_tag: str | None = None
        self._ignored_depth = 0
        self._capture_title = False
        self._capture_heading = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        self._current_tag = tag

        if tag == "script" and "ld+json" in attr_map.get("type", "").lower():
            self._jsonld = True
            self._jsonld_buffer = []
            return
        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if tag == "title":
            self._capture_title = True
            self._buffer = []
        elif tag in HEADING_TAGS:
            self._capture_heading = True
            self._buffer = []
            self._text_parts.append(f"\n{tag.upper()}: ")
            self.heading_levels.append(int(tag[1]))
            self.h1_count += int(tag == "h1")
        elif tag == "meta" and attr_map.get("name", "").lower() == "description":
            self.meta_description = _clean_text(attr_map.get("content", ""))
        elif tag == "meta" and attr_map.get("name", "").lower() in {
            "robots",
            "googlebot",
            "bingbot",
        }:
            self.meta_robots.append(attr_map.get("content", ""))
        elif tag == "link" and attr_map.get("rel", "").lower() == "canonical":
            href = attr_map.get("href")
            if href:
                self.canonical_url = urljoin(self.base_url, href)
        elif tag == "a":
            href = attr_map.get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))
        elif tag == "img":
            self.images.append(
                {"src": urljoin(self.base_url, attr_map.get("src", "")), "alt": attr_map.get("alt")}
            )
        elif tag in BLOCK_TAGS:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return

        if self._ignored_depth:
            return

        if tag == "script" and self._jsonld:
            raw = "".join(self._jsonld_buffer).strip()
            try:
                value = json.loads(raw)
                self.structured_data.append(value if isinstance(value, dict) else {"items": value})
            except (json.JSONDecodeError, TypeError):
                self.structured_data.append({"_invalid": True, "raw": raw[:500]})
            self._jsonld = False
            self._jsonld_buffer = []

        if tag == "title" and self._capture_title:
            self.title = _clean_text(" ".join(self._buffer)) or None
            self._capture_title = False
            self._buffer = []
        elif tag in HEADING_TAGS and self._capture_heading:
            heading = _clean_text(" ".join(self._buffer))
            if heading:
                self.headings.append(heading)
            self._capture_heading = False
            self._buffer = []
            self._text_parts.append("\n")
        elif tag in BLOCK_TAGS or tag in HEADING_TAGS:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._jsonld:
            self._jsonld_buffer.append(data)
            return
        if self._ignored_depth:
            return

        cleaned = _clean_text(data)
        if not cleaned:
            return

        if self._capture_title or self._capture_heading:
            self._buffer.append(cleaned)

        self._text_parts.append(cleaned)
        self._text_parts.append(" ")

    @property
    def body_text(self) -> str:
        return _clean_text("\n".join(self._text_parts))


def parse_html(url: str, html: str) -> ParsedPage:
    parser = _ContentParser(url)
    parser.feed(html)
    parser.close()

    internal_links: list[str] = []
    external_links: list[str] = []
    base_host = urlparse(url).hostname

    for link in dict.fromkeys(parser.links):
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.hostname == base_host:
            internal_links.append(link)
        else:
            external_links.append(link)

    body_text = parser.body_text
    return ParsedPage(
        url=url,
        title=parser.title,
        meta_description=parser.meta_description,
        headings=parser.headings,
        body_text=body_text,
        internal_links=internal_links,
        external_links=external_links,
        canonical_url=parser.canonical_url,
        audit_data={
            "meta_robots": parser.meta_robots,
            "heading_levels": parser.heading_levels,
            "h1_count": parser.h1_count,
            "images": parser.images,
            "structured_data": parser.structured_data,
            "internal_links": internal_links,
            "external_links": external_links,
        },
        content_hash=hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
    )


def _clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()
