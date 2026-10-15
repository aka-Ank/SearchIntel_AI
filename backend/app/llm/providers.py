from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    answer: str
    citation_ids: list[int]
    latency_ms: float = 0.0


class LLMProvider(Protocol):
    def generate_grounded_answer(
        self,
        *,
        question: str,
        prompt: str,
        citation_ids: list[int],
    ) -> LLMResponse:
        """Generate an answer grounded in supplied evidence."""


class MockLLMProvider:
    def generate_grounded_answer(
        self,
        *,
        question: str,
        prompt: str,
        citation_ids: list[int],
    ) -> LLMResponse:
        if not citation_ids:
            return LLMResponse(
                answer=(
                    "The indexed website does not provide enough evidence to answer this question."
                ),
                citation_ids=[],
            )
        first = citation_ids[0]
        return LLMResponse(
            answer=f"Based on the indexed evidence, the answer is supported by citation [{first}].",
            citation_ids=[first],
        )
