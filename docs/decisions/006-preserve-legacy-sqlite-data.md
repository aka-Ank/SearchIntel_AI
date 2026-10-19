# ADR 006: Preserve legacy SQLite data pending ownership recovery

## Status

Accepted; updated 2026-10-18 after user-authorized repair

## Context

The ignored local `backend/searchintel.db` has a valid SQLite structure, but it predates Alembic stamping. It contains one page and one content chunk without tenant, project, or website parent rows. `PRAGMA foreign_key_check` reports a page-to-website violation. A migration rehearsal on a disposable copy succeeds only after stamping the verified `20261003_0001` baseline, and the orphaned page remains.

## Decision

Do not invent tenant, project, or website ownership. Any schema adoption must start with a backup and exact baseline-schema verification. The user explicitly authorized removal of the orphan after backup. A verified pre-repair snapshot is stored at `backend/backups/searchintel.pre-orphan-repair-20261018.db`; the ignored working database now has the orphan page and its dependent chunk removed.

## Consequences

- The pre-repair file remains available at the backup path for recovery and preserves the original page and chunk. The repaired working file is structurally valid and has no foreign-key violations, but it remains a local legacy database and is not treated as the current verified application database.
- Fresh SQLite and PostgreSQL migration tests remain valid, but direct `alembic upgrade head` against this unstamped file fails at the existing `tenants` table.
- No ownership was inferred and no missing parent rows were fabricated. The approved repair pruned only the exact orphan page and its dependent chunk.
