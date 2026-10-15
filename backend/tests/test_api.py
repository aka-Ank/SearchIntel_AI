from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_page.html"


def test_api_indexes_and_searches_fixture_html(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "memory")

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app
    from app.services.container import get_container

    get_settings.cache_clear()
    get_container.cache_clear()
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200

    project = client.post(
        "/api/v1/projects",
        json={
            "tenant_id": "tenant-api",
            "name": "API Project",
            "website_url": "https://example.com/",
        },
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    fetched_project = client.get(
        f"/api/v1/projects/{project_id}",
        params={"tenant_id": "tenant-api"},
    )
    assert fetched_project.status_code == 200

    website = client.post(
        f"/api/v1/projects/{project_id}/websites",
        json={
            "tenant_id": "tenant-api",
            "base_url": "https://example.com/javascript-seo",
            "website_type": "OWN",
        },
    )
    assert website.status_code == 201
    website_id = website.json()["id"]

    indexed = client.post(
        "/api/v1/index/url",
        json={
            "tenant_id": "tenant-api",
            "project_id": project_id,
            "website_id": website_id,
            "url": "https://example.com/javascript-seo",
            "html": FIXTURE.read_text(),
        },
    )
    assert indexed.status_code == 200
    assert indexed.json()["chunk_count"] > 0

    search = client.post(
        "/api/v1/search",
        json={
            "tenant_id": "tenant-api",
            "project_id": project_id,
            "query": "JavaScript hydration",
            "strategy": "hybrid",
            "top_k": 3,
            "include_debug": True,
        },
    )
    assert search.status_code == 200
    results = search.json()["results"]
    assert results
    assert results[0]["tenant_id"] == "tenant-api"
    assert results[0]["debug"]["chunk_id"]

    pages = client.get(
        f"/api/v1/projects/{project_id}/pages",
        params={"tenant_id": "tenant-api"},
    )
    assert pages.status_code == 200
    assert len(pages.json()) == 1

    page = client.get(
        f"/api/v1/pages/{indexed.json()['page_id']}",
        params={"tenant_id": "tenant-api"},
    )
    assert page.status_code == 200
    assert "JavaScript SEO" in page.json()["normalized_text"]

    rag = client.post(
        "/api/v1/rag/query",
        json={
            "tenant_id": "tenant-api",
            "project_id": project_id,
            "question": "What does the page say about hydration?",
            "search_strategy": "hybrid_rerank",
            "top_k": 3,
            "include_debug": True,
        },
    )
    assert rag.status_code == 200
    assert rag.json()["grounded"] is True
    assert rag.json()["citations"]

    import app.services.crawling as crawl_service_module
    import app.services.seo_audits as audit_service_module

    monkeypatch.setattr(crawl_service_module, "_dispatch_task", lambda *_args: "crawl-task")
    queued_crawl = client.post(
        f"/api/v1/websites/{website_id}/crawl",
        json={"tenant_id": "tenant-api", "max_pages": 3, "max_depth": 1, "concurrency": 2},
    )
    assert queued_crawl.status_code == 202
    assert queued_crawl.json()["status"] == "PENDING"
    crawl_id = queued_crawl.json()["id"]
    crawl_status = client.get(f"/api/v1/crawl-jobs/{crawl_id}", params={"tenant_id": "tenant-api"})
    assert crawl_status.status_code == 200
    canceled = client.delete(f"/api/v1/crawl-jobs/{crawl_id}", params={"tenant_id": "tenant-api"})
    assert canceled.status_code == 200 and canceled.json()["status"] == "CANCELED"
    crawl_history = client.get(
        f"/api/v1/websites/{website_id}/crawl-jobs", params={"tenant_id": "tenant-api"}
    )
    assert crawl_history.status_code == 200
    assert crawl_history.json()[0]["id"] == crawl_id

    monkeypatch.setattr(audit_service_module, "_dispatch_task", lambda *_args: "audit-task")
    queued_audit = client.post(
        f"/api/v1/websites/{website_id}/seo-audits", params={"tenant_id": "tenant-api"}
    )
    assert queued_audit.status_code == 202
    audit_id = queued_audit.json()["id"]
    audit_history = client.get(
        f"/api/v1/websites/{website_id}/seo-audits", params={"tenant_id": "tenant-api"}
    )
    assert audit_history.status_code == 200
    assert audit_history.json()[0]["id"] == audit_id
    assert (
        client.get(
            f"/api/v1/seo-audits/{audit_id}/summary", params={"tenant_id": "tenant-api"}
        ).status_code
        == 200
    )


def test_explicit_local_url_permission_is_applied_to_website_registration(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'local-url.db'}")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "memory")
    monkeypatch.setenv("ALLOW_LOCAL_URLS", "true")

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app
    from app.services.container import get_container

    get_settings.cache_clear()
    get_container.cache_clear()
    client = TestClient(app)
    project = client.post(
        "/api/v1/projects",
        json={"tenant_id": "local-test", "name": "Loopback", "website_url": None},
    )
    assert project.status_code == 201
    website = client.post(
        f"/api/v1/projects/{project.json()['id']}/websites",
        json={
            "tenant_id": "local-test",
            "base_url": "http://127.0.0.1:8888/",
            "website_type": "OWN",
        },
    )
    assert website.status_code == 201
    get_container.cache_clear()
    get_settings.cache_clear()
