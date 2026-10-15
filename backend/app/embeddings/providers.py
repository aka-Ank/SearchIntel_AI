from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")


@dataclass(frozen=True)
class EmbeddingMetadata:
    provider: str
    model: str
    dimension: int
    version: str


class EmbeddingProvider(Protocol):
    metadata: EmbeddingMetadata
    dimensions: int

    def embed_text(self, text: str) -> list[float]:
        """Embed a single document text value."""

    def embed_query(self, query: str) -> list[float]:
        """Embed a query text value."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple document text values."""


class DeterministicEmbeddingProvider:
    """Deterministic local embedding provider for tests and offline development."""

    def __init__(self, dimensions: int = 64, version: str = "deterministic-v1") -> None:
        self.dimensions = dimensions
        self.metadata = EmbeddingMetadata(
            provider="deterministic",
            model="hash-token-projection",
            dimension=dimensions,
            version=version,
        )

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize(vector)

    def embed_query(self, query: str) -> list[float]:
        return self.embed_text(query)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class SentenceTransformerEmbeddingProvider:
    """Sentence-transformers embedding provider for local production use."""

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-small-en-v1.5",
        version: str | None = None,
        normalize_embeddings: bool = True,
        query_prefix: str = "Represent this sentence for searching relevant passages: ",
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Install optional model dependencies with `pip install -e '.[models]'` "
                "to use sentence-transformers embeddings."
            ) from exc

        self._model = SentenceTransformer(model_name)
        self._normalize_embeddings = normalize_embeddings
        self._query_prefix = query_prefix
        self.dimensions = int(self._model.get_sentence_embedding_dimension())
        self.metadata = EmbeddingMetadata(
            provider="sentence_transformers",
            model=model_name,
            dimension=self.dimensions,
            version=version or model_name.replace("/", "__"),
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_query(self, query: str) -> list[float]:
        return _as_float_list(
            self._model.encode(
                [f"{self._query_prefix}{query}"],
                normalize_embeddings=self._normalize_embeddings,
            )[0]
        )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=self._normalize_embeddings)
        return [_as_float_list(vector) for vector in vectors]


HashEmbeddingProvider = DeterministicEmbeddingProvider


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vectors must have equal dimensions")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _as_float_list(vector: Iterable[Any]) -> list[float]:
    return [float(value) for value in vector]
