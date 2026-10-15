from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.schemas.content import ContentChunk

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")


@dataclass(frozen=True)
class BM25Hit:
    chunk: ContentChunk
    score: float


class BM25Index:
    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._chunks: dict[str, ContentChunk] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequencies: dict[str, int] = defaultdict(int)
        self._document_lengths: dict[str, int] = {}

    def rebuild(self, chunks: list[ContentChunk]) -> None:
        self._chunks.clear()
        self._term_frequencies.clear()
        self._document_frequencies.clear()
        self._document_lengths.clear()
        for chunk in chunks:
            self.upsert(chunk)

    def upsert(self, chunk: ContentChunk) -> None:
        old_terms = set(self._term_frequencies.get(chunk.id, Counter()).keys())
        for term in old_terms:
            self._document_frequencies[term] -= 1

        tokens = tokenize(chunk.text)
        frequencies = Counter(tokens)
        self._chunks[chunk.id] = chunk
        self._term_frequencies[chunk.id] = frequencies
        self._document_lengths[chunk.id] = len(tokens)
        for term in frequencies:
            self._document_frequencies[term] += 1

    def search(
        self,
        *,
        query: str,
        tenant_id: str,
        project_id: str,
        top_k: int,
        website_ids: list[str] | None = None,
    ) -> list[BM25Hit]:
        query_terms = tokenize(query)
        if not query_terms:
            return []

        average_length = self._average_document_length()
        hits: list[BM25Hit] = []
        for chunk_id, chunk in self._chunks.items():
            if chunk.tenant_id != tenant_id or chunk.project_id != project_id:
                continue
            if website_ids and chunk.website_id not in website_ids:
                continue
            score = self._score_chunk(chunk_id, query_terms, average_length)
            if score > 0:
                hits.append(BM25Hit(chunk=chunk, score=score))

        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    def _score_chunk(self, chunk_id: str, query_terms: list[str], average_length: float) -> float:
        score = 0.0
        total_documents = max(len(self._chunks), 1)
        frequencies = self._term_frequencies[chunk_id]
        document_length = self._document_lengths[chunk_id]

        for term in query_terms:
            term_frequency = frequencies.get(term, 0)
            if term_frequency == 0:
                continue
            document_frequency = self._document_frequencies.get(term, 0)
            idf = math.log(
                1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * document_length / max(average_length, 1)
            )
            score += idf * (term_frequency * (self.k1 + 1)) / denominator
        return score

    def _average_document_length(self) -> float:
        if not self._document_lengths:
            return 0.0
        return sum(self._document_lengths.values()) / len(self._document_lengths)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())
