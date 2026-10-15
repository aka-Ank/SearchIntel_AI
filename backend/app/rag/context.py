from __future__ import annotations

from dataclasses import dataclass

from app.schemas.rag import Citation
from app.schemas.retrieval import RetrievedChunkResult


@dataclass(frozen=True)
class EvidenceItem:
    citation_number: int
    chunk: RetrievedChunkResult


@dataclass(frozen=True)
class BuiltContext:
    prompt_context: str
    evidence: list[EvidenceItem]
    approximate_chars: int


class ContextBuilder:
    def __init__(self, *, max_chars: int) -> None:
        self._max_chars = max_chars

    def build(self, chunks: list[RetrievedChunkResult]) -> BuiltContext:
        seen: set[str] = set()
        evidence: list[EvidenceItem] = []
        parts: list[str] = []
        total = 0
        for chunk in chunks:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            text = chunk.content.strip()
            if not text:
                continue
            citation_number = len(evidence) + 1
            item_text = (
                f"[{citation_number}] URL: {chunk.url}\n"
                f"Title: {chunk.title or 'Untitled'}\n"
                f"Page ID: {chunk.page_id}\n"
                f"Chunk ID: {chunk.chunk_id}\n"
                f"Heading: {' > '.join(chunk.heading_path) if chunk.heading_path else 'None'}\n"
                f"Evidence: {text}\n"
            )
            if total + len(item_text) > self._max_chars and evidence:
                break
            parts.append(item_text)
            total += len(item_text)
            evidence.append(EvidenceItem(citation_number=citation_number, chunk=chunk))
        return BuiltContext(
            prompt_context="\n".join(parts),
            evidence=evidence,
            approximate_chars=total,
        )


def citation_from_evidence(item: EvidenceItem) -> Citation:
    chunk = item.chunk
    return Citation(
        citation_number=item.citation_number,
        page_title=chunk.title,
        url=chunk.url,
        page_id=chunk.page_id,
        chunk_id=chunk.chunk_id,
        heading_path=chunk.heading_path,
        supporting_snippet=chunk.snippet,
    )
