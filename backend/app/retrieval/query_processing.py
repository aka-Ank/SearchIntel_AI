from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessedQuery:
    original_query: str
    lexical_query: str
    semantic_query: str


class QueryProcessor:
    def process(self, query: str) -> ProcessedQuery:
        normalized = " ".join(query.strip().split())
        return ProcessedQuery(
            original_query=query,
            lexical_query=normalized,
            semantic_query=normalized,
        )
