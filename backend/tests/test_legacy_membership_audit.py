from __future__ import annotations

import json
import os
import sys
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, delete, func, insert, select
from sqlalchemy.orm import Session

from app.cli import main
from app.core.config import get_settings
from app.maintenance.legacy_memberships import audit_unassigned_tenants
from app.models.tenant import Tenant


def test_legacy_membership_audit_cli_reports_unassigned_tenants_without_writes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    database_path = tmp_path / "legacy-tenants.db"
    engine = create_engine(f"sqlite:///{database_path}")
    metadata = MetaData()
    tenants = Table(
        "tenants",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
    )
    projects = Table(
        "projects",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
    )
    websites = Table(
        "websites",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
    )
    memberships = Table(
        "tenant_memberships",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(tenants),
            [
                {"id": "legacy-unassigned", "name": "Legacy"},
                {"id": "already-mapped", "name": "Mapped"},
            ],
        )
        connection.execute(
            insert(projects), [{"id": "project-old", "tenant_id": "legacy-unassigned"}]
        )
        connection.execute(
            insert(websites), [{"id": "site-old", "tenant_id": "legacy-unassigned"}]
        )
        connection.execute(
            insert(memberships), [{"id": "membership", "tenant_id": "already-mapped"}]
        )

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys, "argv", ["searchintel", "audit-legacy-memberships", "--format", "json"]
    )
    main()
    report = json.loads(capsys.readouterr().out)
    get_settings.cache_clear()
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(tenants)) == 2
        assert connection.scalar(select(func.count()).select_from(projects)) == 1
        assert connection.scalar(select(func.count()).select_from(websites)) == 1
        assert connection.scalar(select(func.count()).select_from(memberships)) == 1
    engine.dispose()

    assert report["read_only"] is True
    assert report["tenant_count"] == 2
    assert report["tenants_without_memberships"] == 1
    assert report["unassigned_tenants"] == [
        {
            "id": "legacy-unassigned",
            "name": "Legacy",
            "project_count": 1,
            "website_count": 1,
            "membership_count": 0,
        }
    ]
    assert report["note"] == "This report does not infer ownership or create memberships."


def test_legacy_membership_audit_refuses_to_create_missing_database(tmp_path) -> None:
    database_path = tmp_path / "missing.db"
    with pytest.raises(RuntimeError, match="refusing to create it"):
        audit_unassigned_tenants(f"sqlite:///{database_path}")
    assert not database_path.exists()


def test_legacy_membership_audit_uses_read_only_postgresql_transaction() -> None:
    database_url = os.getenv("SEARCHINTEL_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set SEARCHINTEL_TEST_DATABASE_URL to run the PostgreSQL audit integration")

    tenant_id = str(uuid4())
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            session.add(Tenant(id=tenant_id, name="Temporary audit fixture"))
            session.commit()

        report = audit_unassigned_tenants(database_url)
        tenant = next(row for row in report["unassigned_tenants"] if row["id"] == tenant_id)
        assert tenant["membership_count"] == 0
        assert tenant["project_count"] == 0
    finally:
        with engine.begin() as connection:
            connection.execute(delete(Tenant).where(Tenant.id == tenant_id))
        engine.dispose()
