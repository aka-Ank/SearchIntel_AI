from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, func, inspect, literal, select
from sqlalchemy.engine import make_url
from sqlalchemy.sql.elements import ColumnElement


def audit_unassigned_tenants(database_url: str) -> dict[str, Any]:
    """Report tenants with no membership without creating tables or changing stored data."""
    url = make_url(database_url)
    connect_args: dict[str, bool] = {}
    if url.get_backend_name() == "sqlite":
        database = url.database
        if database in {None, ":memory:"}:
            raise RuntimeError("Read-only audit requires an existing SQLite database file")
        if database.startswith("file:"):
            database_path = database.removeprefix("file:").split("?", maxsplit=1)[0]
        else:
            database_path = database
            url = url.set(database=f"file:{database}")
        if not Path(database_path).is_file():
            raise RuntimeError("SQLite database file does not exist; refusing to create it")
        url = url.update_query_dict({"mode": "ro", "uri": "true"})
        connect_args["uri"] = True
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            table_names = set(inspect(connection).get_table_names())
            if "tenants" not in table_names:
                raise RuntimeError(
                    "Database has no tenants table; apply the project migrations first"
                )

            metadata = MetaData()
            tenants = Table("tenants", metadata, autoload_with=connection)
            projects = (
                Table("projects", metadata, autoload_with=connection)
                if "projects" in table_names
                else None
            )
            websites = (
                Table("websites", metadata, autoload_with=connection)
                if "websites" in table_names
                else None
            )
            memberships = (
                Table("tenant_memberships", metadata, autoload_with=connection)
                if "tenant_memberships" in table_names
                else None
            )

            project_count: ColumnElement[Any] = (
                select(func.count())
                .select_from(projects)
                .where(projects.c.tenant_id == tenants.c.id)
                .scalar_subquery()
                if projects is not None
                else literal(0)
            )
            if websites is not None and "tenant_id" in websites.c:
                website_count: ColumnElement[Any] = (
                    select(func.count())
                    .select_from(websites)
                    .where(websites.c.tenant_id == tenants.c.id)
                    .scalar_subquery()
                )
            elif websites is not None and projects is not None:
                website_count = (
                    select(func.count())
                    .select_from(websites.join(projects, websites.c.project_id == projects.c.id))
                    .where(projects.c.tenant_id == tenants.c.id)
                    .scalar_subquery()
                )
            else:
                website_count = literal(0)

            membership_count = (
                select(func.count())
                .select_from(memberships)
                .where(memberships.c.tenant_id == tenants.c.id)
                .scalar_subquery()
                if memberships is not None
                else literal(0)
            )
            statement = select(
                tenants.c.id,
                tenants.c.name,
                project_count.label("project_count"),
                website_count.label("website_count"),
                membership_count.label("membership_count"),
            ).order_by(tenants.c.name, tenants.c.id)
            tenant_rows = [dict(row._mapping) for row in connection.execute(statement)]

        unassigned = [row for row in tenant_rows if row["membership_count"] == 0]
        return {
            "read_only": True,
            "tenant_count": len(tenant_rows),
            "tenants_without_memberships": len(unassigned),
            "tenants": tenant_rows,
            "unassigned_tenants": unassigned,
            "note": "This report does not infer ownership or create memberships.",
        }
    finally:
        engine.dispose()
