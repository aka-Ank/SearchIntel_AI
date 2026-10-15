from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.main import app
from app.retrieval.vector_store import versioned_collection_name
from app.schemas.content import ContentChunk
from app.services.container import get_container


def _register(client: TestClient, email: str) -> None:
    password = "integration-test-password"
    registration = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert login.status_code == 204
    client.headers.update({"X-CSRF-Token": client.cookies.get("searchintel_csrf", "")})


def _chunk(*, chunk_id: str, tenant_id: str, project_id: str, text: str) -> ContentChunk:
    return ContentChunk(
        id=chunk_id,
        tenant_id=tenant_id,
        project_id=project_id,
        website_id="shared-website-id",
        page_id=f"page-{chunk_id}",
        url=f"https://example.test/{chunk_id}",
        title=chunk_id,
        heading_path=[],
        chunk_index=0,
        text=text,
        char_count=len(text),
    )


def test_authenticated_search_cannot_retrieve_another_tenants_qdrant_vector(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    qdrant_url = os.getenv("SEARCHINTEL_TEST_QDRANT_URL")
    if not qdrant_url:
        pytest.skip("Set SEARCHINTEL_TEST_QDRANT_URL to run Qdrant API integration tests")

    database_url = os.getenv("SEARCHINTEL_TEST_DATABASE_URL") or (
        f"sqlite:///{tmp_path / 'api-qdrant.db'}"
    )
    collection_base = f"searchintel_authenticated_isolation_{uuid4().hex}"
    embedding_version = f"integration-{uuid4().hex}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("QDRANT_URL", qdrant_url)
    monkeypatch.setenv("QDRANT_COLLECTION", collection_base)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "64")
    monkeypatch.setenv("EMBEDDING_VERSION", embedding_version)
    monkeypatch.setenv("AUTH_SECRET", "integration-test-secret-0123456789-0123456789")
    monkeypatch.setenv("APP_ENV", "local")
    get_settings.cache_clear()
    get_container.cache_clear()

    collection_name = versioned_collection_name(collection_base, embedding_version)
    qdrant = QdrantClient(url=qdrant_url)
    try:
        with TestClient(app) as client:
            _register(client, f"tenant-a-{uuid4().hex}@example.com")
            tenant_a = client.post("/api/v1/tenants", json={"name": "Tenant A"})
            assert tenant_a.status_code == 201
            tenant_a_id = tenant_a.json()["id"]
            project_a = client.post(
                "/api/v1/projects", json={"tenant_id": tenant_a_id, "name": "Project A"}
            )
            assert project_a.status_code == 201
            project_a_id = project_a.json()["id"]

            owner_chunk = _chunk(
                chunk_id=f"{uuid4().hex}-owner",
                tenant_id=tenant_a_id,
                project_id=project_a_id,
                text="private zebra migration plan owned by tenant A",
            )
            get_container().retrieval.index_chunks([owner_chunk])

            owner_search = client.post(
                "/api/v1/search",
                json={
                    "tenant_id": tenant_a_id,
                    "project_id": project_a_id,
                    "query": "private zebra migration plan",
                    "strategy": "vector",
                },
            )
            assert owner_search.status_code == 200
            assert [item["chunk_id"] for item in owner_search.json()["results"]] == [
                owner_chunk.id
            ]

            assert client.post("/api/v1/auth/logout").status_code == 204
            _register(client, f"tenant-b-{uuid4().hex}@example.com")
            tenant_b = client.post("/api/v1/tenants", json={"name": "Tenant B"})
            assert tenant_b.status_code == 201
            tenant_b_id = tenant_b.json()["id"]
            project_b = client.post(
                "/api/v1/projects", json={"tenant_id": tenant_b_id, "name": "Project B"}
            )
            assert project_b.status_code == 201
            project_b_id = project_b.json()["id"]

            cross_tenant_chunk = _chunk(
                chunk_id=f"{uuid4().hex}-foreign",
                tenant_id=tenant_a_id,
                project_id=project_b_id,
                text="private zebra migration plan from tenant A with tenant B project id",
            )
            get_container().retrieval.index_chunks([cross_tenant_chunk])

            foreign_project = client.post(
                "/api/v1/search",
                json={
                    "tenant_id": tenant_a_id,
                    "project_id": project_a_id,
                    "query": "private zebra migration plan",
                    "strategy": "vector",
                },
            )
            assert foreign_project.status_code == 404

            contaminated_project_search = client.post(
                "/api/v1/search",
                json={
                    "tenant_id": tenant_b_id,
                    "project_id": project_b_id,
                    "query": "private zebra migration plan",
                    "strategy": "vector",
                },
            )
            assert contaminated_project_search.status_code == 200
            assert contaminated_project_search.json()["results"] == []
    finally:
        if any(
            collection.name == collection_name
            for collection in qdrant.get_collections().collections
        ):
            qdrant.delete_collection(collection_name=collection_name)
        qdrant.close()
        get_container.cache_clear()
        get_settings.cache_clear()
