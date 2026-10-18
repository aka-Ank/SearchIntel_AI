# ADR 006: Preserve legacy SQLite data pending ownership recovery

## Status

Accepted

## Context

The ignored local `backend/searchintel.db` has a valid SQLite structure, but it predates Alembic stamping. It contains one page and one content chunk without tenant, project, or website parent rows. `PRAGMA foreign_key_check` reports a page-to-website violation. A migration rehearsal on a disposable copy succeeds only after stamping the verified `20261003_0001` baseline, and the orphaned page remains.

## Decision

Keep the original database unchanged. Do not delete its page/chunk or invent tenant, project, or website ownership. Any future schema adoption must start with a backup and exact baseline-schema verification. Resolve the orphan only from trusted parent metadata or after explicit authorization to remove it.

## Consequences

- The file remains available for recovery and is not treated as the current verified application database.
- Fresh SQLite and PostgreSQL migration tests remain valid, but direct `alembic upgrade head` against this unstamped file fails at the existing `tenants` table.
- Local database repair requires a trusted source for its missing parent rows or a user-approved data-pruning plan.
