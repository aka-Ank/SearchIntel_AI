from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.embeddings.providers import EmbeddingMetadata, cosine_similarity
from app.schemas.content import ContentChunk


@dataclass(frozen=True)
class VectorSearchHit:
    chunk: ContentChunk
    score: float


class VectorStore(Protocol):
    def upsert(
        self,
        chunk: ContentChunk,
        vector: list[float],
        *,
        metadata: EmbeddingMetadata,
    ) -> None:
        """Insert or replace one chunk vector."""

    def search(
        self,
        *,
        query_vector: list[float],
        tenant_id: str,
        project_id: str,
        top_k: int,
        website_ids: list[str] | None = None,
        metadata: EmbeddingMetadata | None = None,
    ) -> list[VectorSearchHit]:
        """Search vectors with tenant and project filters."""


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._records: dict[str, tuple[ContentChunk, list[float]]] = {}

    def upsert(
        self,
        chunk: ContentChunk,
        vector: list[float],
        *,
        metadata: EmbeddingMetadata,
    ) -> None:
        self._records[chunk.id] = (chunk, vector)

    def search(
        self,
        *,
        query_vector: list[float],
        tenant_id: str,
        project_id: str,
        top_k: int,
        website_ids: list[str] | None = None,
        metadata: EmbeddingMetadata | None = None,
    ) -> list[VectorSearchHit]:
        hits: list[VectorSearchHit] = []
        for chunk, vector in self._records.values():
            if chunk.tenant_id != tenant_id or chunk.project_id != project_id:
                continue
            if website_ids and chunk.website_id not in website_ids:
                continue
            hits.append(VectorSearchHit(chunk=chunk, score=cosine_similarity(query_vector, vector)))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]


class QdrantVectorStore:
    def __init__(
        self,
        *,
        url: str,
        collection_name: str,
        vector_size: int,
        embedding_version: str,
    ) -> None:
        from qdrant_client import QdrantClient, models

        self._models: Any = models
        self._client: Any = QdrantClient(url=url)
        self._collection_name = versioned_collection_name(collection_name, embedding_version)
        self._vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self._client.get_collections().collections
        if any(collection.name == self._collection_name for collection in collections):
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=self._models.VectorParams(
                size=self._vector_size,
                distance=self._models.Distance.COSINE,
            ),
        )

    def upsert(
        self,
        chunk: ContentChunk,
        vector: list[float],
        *,
        metadata: EmbeddingMetadata,
    ) -> None:
        payload = {
            "tenant_id": chunk.tenant_id,
            "project_id": chunk.project_id,
            "website_id": chunk.website_id,
            "page_id": chunk.page_id,
            "chunk_id": chunk.id,
            "url": chunk.url,
            "title": chunk.title,
            "heading_path": chunk.heading_path,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "char_count": chunk.char_count,
            "embedding_provider": metadata.provider,
            "embedding_model": metadata.model,
            "embedding_dimension": metadata.dimension,
            "embedding_version": metadata.version,
        }
        self._client.upsert(
            collection_name=self._collection_name,
            points=[
                self._models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, chunk.id)),
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    def search(
        self,
        *,
        query_vector: list[float],
        tenant_id: str,
        project_id: str,
        top_k: int,
        website_ids: list[str] | None = None,
        metadata: EmbeddingMetadata | None = None,
    ) -> list[VectorSearchHit]:
        conditions = [
            self._models.FieldCondition(
                key="tenant_id",
                match=self._models.MatchValue(value=tenant_id),
            ),
            self._models.FieldCondition(
                key="project_id",
                match=self._models.MatchValue(value=project_id),
            ),
        ]
        if website_ids:
            conditions.append(
                self._models.FieldCondition(
                    key="website_id",
                    match=self._models.MatchAny(any=website_ids),
                )
            )
        if metadata is not None:
            conditions.extend(
                [
                    self._models.FieldCondition(
                        key="embedding_provider",
                        match=self._models.MatchValue(value=metadata.provider),
                    ),
                    self._models.FieldCondition(
                        key="embedding_model",
                        match=self._models.MatchValue(value=metadata.model),
                    ),
                    self._models.FieldCondition(
                        key="embedding_dimension",
                        match=self._models.MatchValue(value=metadata.dimension),
                    ),
                    self._models.FieldCondition(
                        key="embedding_version",
                        match=self._models.MatchValue(value=metadata.version),
                    ),
                ]
            )
        query_response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            query_filter=self._models.Filter(must=conditions),
            limit=top_k,
            with_payload=True,
        )
        hits: list[VectorSearchHit] = []
        for point in query_response.points:
            payload = point.payload or {}
            chunk = ContentChunk(
                id=str(payload["chunk_id"]),
                tenant_id=str(payload["tenant_id"]),
                project_id=str(payload["project_id"]),
                website_id=str(payload["website_id"]),
                page_id=str(payload["page_id"]),
                url=str(payload["url"]),
                title=payload.get("title"),
                heading_path=list(payload.get("heading_path") or []),
                chunk_index=int(payload.get("chunk_index") or 0),
                text=str(payload.get("text") or ""),
                char_count=int(payload.get("char_count") or 0),
            )
            hits.append(VectorSearchHit(chunk=chunk, score=float(point.score)))
        return hits


def versioned_collection_name(base_name: str, embedding_version: str) -> str:
    safe_version = re.sub(r"[^a-zA-Z0-9_-]+", "_", embedding_version)
    return f"{base_name}_{safe_version}"
