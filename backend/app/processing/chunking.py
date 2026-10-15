from __future__ import annotations

import hashlib
import re

from app.schemas.content import ContentChunk, ParsedPage

SECTION_RE = re.compile(r"\n?H[1-6]:\s+")


class StructureAwareChunker:
    def __init__(self, *, target_chars: int = 900, max_chars: int = 1400) -> None:
        self.target_chars = target_chars
        self.max_chars = max_chars

    def chunk_page(
        self,
        *,
        tenant_id: str,
        project_id: str,
        website_id: str,
        page_id: str,
        page: ParsedPage,
    ) -> list[ContentChunk]:
        sections = self._split_sections(page.body_text, page.headings)
        chunks: list[ContentChunk] = []
        current_text = ""
        current_headings: list[str] = []

        for heading_path, text in sections:
            if not text:
                continue
            if len(current_text) + len(text) > self.target_chars and current_text:
                chunks.append(
                    self._build_chunk(
                        tenant_id,
                        project_id,
                        website_id,
                        page_id,
                        page,
                        len(chunks),
                        current_text,
                        current_headings,
                    )
                )
                current_text = ""
                current_headings = []

            if len(text) > self.max_chars:
                for part in self._split_long_text(text):
                    chunks.append(
                        self._build_chunk(
                            tenant_id,
                            project_id,
                            website_id,
                            page_id,
                            page,
                            len(chunks),
                            part,
                            heading_path,
                        )
                    )
                continue

            current_text = f"{current_text}\n\n{text}".strip()
            current_headings = heading_path or current_headings

        if current_text:
            chunks.append(
                self._build_chunk(
                    tenant_id,
                    project_id,
                    website_id,
                    page_id,
                    page,
                    len(chunks),
                    current_text,
                    current_headings,
                )
            )

        return chunks

    def _split_sections(self, text: str, headings: list[str]) -> list[tuple[list[str], str]]:
        paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
        if not paragraphs:
            return []

        sections: list[tuple[list[str], str]] = []
        heading_index = 0
        current_heading: list[str] = []

        for paragraph in paragraphs:
            if heading_index < len(headings) and headings[heading_index] in paragraph:
                current_heading = [headings[heading_index]]
                heading_index += 1
                continue
            sections.append((current_heading, paragraph))

        if not sections:
            return [([], text)]
        return sections

    def _split_long_text(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        parts: list[str] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > self.max_chars and current:
                parts.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            parts.append(current.strip())
        return parts

    def _build_chunk(
        self,
        tenant_id: str,
        project_id: str,
        website_id: str,
        page_id: str,
        page: ParsedPage,
        chunk_index: int,
        text: str,
        heading_path: list[str],
    ) -> ContentChunk:
        chunk_id = hashlib.sha256(
            f"{tenant_id}:{project_id}:{page_id}:{chunk_index}:{text}".encode()
        ).hexdigest()[:24]
        return ContentChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            project_id=project_id,
            website_id=website_id,
            page_id=page_id,
            url=page.url,
            title=page.title,
            heading_path=heading_path,
            chunk_index=chunk_index,
            text=text,
            char_count=len(text),
        )
