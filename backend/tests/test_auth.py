from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import require_tenant_role
from app.main import app
from app.models.auth import TenantMembership
from app.services.container import get_container


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-test-password"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "secure-test-password"},
    )
    assert login.status_code == 204
    cookie_header = login.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    client.headers.update({"X-CSRF-Token": client.cookies.get("searchintel_csrf", "")})
    return response.json()


def test_auth_cookie_tenant_isolation_and_role_enforcement(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "memory")
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-that-is-at-least-32-bytes-long")

    from app.core.config import get_settings

    get_settings.cache_clear()
    get_container.cache_clear()

    with TestClient(app) as unauthenticated:
        assert unauthenticated.get("/api/v1/tenants").status_code == 401

    alice = TestClient(app)
    alice_user = _register(alice, "alice@example.com")
    alice_tenant = alice.post("/api/v1/tenants", json={"name": "Alice tenant"})
    assert alice_tenant.status_code == 201
    tenant_a = alice_tenant.json()["id"]
    created_project = alice.post(
        "/api/v1/projects", json={"tenant_id": tenant_a, "name": "Alice project"}
    )
    assert created_project.status_code == 201

    bob = TestClient(app)
    _register(bob, "bob@example.com")
    bob_tenant = bob.post("/api/v1/tenants", json={"name": "Bob tenant"})
    assert bob_tenant.status_code == 201
    tenant_b = bob_tenant.json()["id"]

    response = alice.get("/api/v1/projects", params={"tenant_id": tenant_b})
    assert response.status_code == 404
    assert alice.get("/api/v1/projects", params={"tenant_id": tenant_a}).status_code == 200
    added = alice.post(
        f"/api/v1/tenants/{tenant_a}/members",
        json={"email": "bob@example.com", "role": "viewer"},
    )
    assert added.status_code == 201
    assert bob.get("/api/v1/projects", params={"tenant_id": tenant_a}).status_code == 200
    assert (
        bob.post(
            "/api/v1/projects", json={"tenant_id": tenant_a, "name": "Viewer denied"}
        ).status_code
        == 404
    )
    promoted = alice.post(
        f"/api/v1/tenants/{tenant_a}/members",
        json={"email": "bob@example.com", "role": "editor"},
    )
    assert promoted.status_code == 201
    assert (
        bob.post(
            "/api/v1/projects", json={"tenant_id": tenant_a, "name": "Editor allowed"}
        ).status_code
        == 201
    )

    with get_container().session_factory.begin() as session:
        membership = session.scalar(
            select(TenantMembership).where(
                TenantMembership.user_id == alice_user["id"],
                TenantMembership.tenant_id == tenant_a,
            )
        )
        assert membership is not None
        membership.role = "viewer"

    denied = alice.post(
        "/api/v1/projects", json={"tenant_id": tenant_a, "name": "Should be denied"}
    )
    assert denied.status_code == 404
    active_token = alice.cookies.get("searchintel_session")
    assert alice.post("/api/v1/auth/logout").status_code == 204
    assert alice.get("/api/v1/tenants").status_code == 401
    assert active_token
    alice.cookies.set("searchintel_session", active_token)
    assert alice.get("/api/v1/tenants").status_code == 401
    alice.close()
    bob.close()


def test_tenant_role_helper_rejects_unknown_role() -> None:
    try:
        require_tenant_role(user=None, tenant_id="tenant", minimum_role="superuser")  # type: ignore[arg-type]
    except ValueError as error:
        assert "Unknown tenant role" in str(error)
    else:
        raise AssertionError("unknown authorization roles must be rejected")


def test_cookie_authenticated_write_requires_csrf_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'csrf.db'}")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "memory")
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-that-is-at-least-32-bytes-long")
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_container.cache_clear()
    client = TestClient(app)
    _register(client, "csrf@example.com")
    client.headers.pop("X-CSRF-Token")
    denied = client.post("/api/v1/tenants", json={"name": "CSRF blocked"})
    assert denied.status_code == 403
    client.close()


def test_registration_rate_limit_returns_retry_after(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'rate-limit.db'}")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "memory")
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-that-is-at-least-32-bytes-long")
    monkeypatch.setenv("AUTH_REGISTER_RATE_LIMIT", "2")
    monkeypatch.setenv("AUTH_REGISTER_RATE_WINDOW_SECONDS", "60")
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_container.cache_clear()
    with TestClient(app) as client:
        for index in range(2):
            response = client.post(
                "/api/v1/auth/register",
                json={"email": f"rate-{index}@example.com", "password": "secure-test-password"},
            )
            assert response.status_code == 201
        limited = client.post(
            "/api/v1/auth/register",
            json={"email": "rate-3@example.com", "password": "secure-test-password"},
        )
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "60"
