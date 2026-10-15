from __future__ import annotations

import os
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient

from app.embeddings.providers import HashEmbeddingProvider
from app.retrieval.vector_store import QdrantVectorStore, versioned_collection_name
from app.schemas.content import ContentChunk


def _chunk(*, chunk_id: str, tenant_id: str, text: str) -> ContentChunk:
    return ContentChunk(
        id=chunk_id,
        tenant_id=tenant_id,
        project_id="shared-project-id",
        website_id="shared-website-id",
        page_id=f"page-{chunk_id}",
        url=f"https://example.test/{chunk_id}",
        title=chunk_id,
        heading_path=[],
        chunk_index=0,
        text=text,
        char_count=len(text),
    )


def test_qdrant_search_isolates_tenants() -> None:
    qdrant_url = os.getenv("SEARCHINTEL_TEST_QDRANT_URL")
    if not qdrant_url:
        pytest.skip("Set SEARCHINTEL_TEST_QDRANT_URL to run isolated Qdrant integration tests")

    collection_base = f"searchintel_tenant_isolation_{uuid4().hex}"
    embedding = HashEmbeddingProvider(dimensions=64)
    store = QdrantVectorStore(
        url=qdrant_url,
        collection_name=collection_base,
        vector_size=embedding.metadata.dimension,
        embedding_version="integration-test",
    )
    collection_name = versioned_collection_name(collection_base, "integration-test")
    qdrant = QdrantClient(url=qdrant_url)
    try:
        private_a = _chunk(
            chunk_id=f"{uuid4().hex}-a",
            tenant_id="tenant-a",
            text="Confidential migration strategy for tenant A",
        )
        private_b = _chunk(
            chunk_id=f"{uuid4().hex}-b",
            tenant_id="tenant-b",
            text="Confidential migration strategy for tenant B",
        )
        for chunk in (private_a, private_b):
            store.upsert(chunk, embedding.embed_query(chunk.text), metadata=embedding.metadata)

        query = embedding.embed_query("confidential migration strategy")
        tenant_a_hits = store.search(
            query_vector=query,
            tenant_id="tenant-a",
            project_id="shared-project-id",
            top_k=5,
            metadata=embedding.metadata,
        )
        tenant_b_hits = store.search(
            query_vector=query,
            tenant_id="tenant-b",
            project_id="shared-project-id",
            top_k=5,
            metadata=embedding.metadata,
        )
        assert [hit.chunk.id for hit in tenant_a_hits] == [private_a.id]
        assert [hit.chunk.id for hit in tenant_b_hits] == [private_b.id]
        assert all(hit.chunk.tenant_id == "tenant-a" for hit in tenant_a_hits)
        assert all(hit.chunk.tenant_id == "tenant-b" for hit in tenant_b_hits)
    finally:
        qdrant.delete_collection(collection_name=collection_name)
        qdrant.close()
        store._client.close()
