# SearchIntel AI project status

Updated: 2026-10-15

## Current checkpoint

- Recovery: complete. The 66-file available archive was restored without modifying the archive.
- Existing crawl-to-search and grounded RAG baseline: preserved; regression suite passes.
- Async crawl worker: Celery/Redis with persisted PostgreSQL jobs. Retry, stale recovery, cancellation, deduplication, and failure-state tests pass. A full Linux/Python 3.12 prefork crawl-to-Qdrant/search/RAG/audit workflow passed; macOS/Python 3.14 keeps the solo pool fallback.
- Readiness endpoint: reports database, Redis, and a live Celery worker with `503` when not ready; unit checks and a live `200` check passed.
- Technical SEO audits: deterministic rules, relational persistence, Celery dispatch, tenant-scoped APIs, and audit history pass unit checks and a live audit (3 pages, 27 findings).
- Frontend: Next.js dashboard implements auth, project/site management, crawl, audits, page browsing, search, RAG, and competitor coverage. Playwright E2E passes for auth, tenant isolation, crawl, audit, citations, competitor crawl, and API failure display.
- Controlled integration: isolated PostgreSQL, Redis, and Qdrant containers completed migration, crawl, indexing, hybrid retrieval, grounded mock RAG, and SEO audit. Existing stopped `seo-*` containers and volumes were left untouched.
- Authentication: FastAPI Users registration/login/logout with Redis-backed opaque sessions, HttpOnly, SameSite cookies, and CSRF validation; membership-backed tenant roles protect project, website, crawl, audit, page, index, search, and RAG routes. SQLite tests, PostgreSQL/Redis session revocation and tenant checks, browser E2E, and Redis-backed login/registration/crawl/audit throttles pass. A unique `AUTH_SECRET` of at least 32 characters is required. Legacy membership backfill remains open.
- Crawler SSRF hardening: validated DNS answers are pinned to the socket connection; unsafe redirects and private destinations are rejected. Controlled DNS-rebinding tests and the fixture-site browser crawl pass. No external website crawl was performed.
- Vector isolation: isolated PostgreSQL/Qdrant integration verified authenticated owner retrieval, foreign project denial, and filtering of a mismatched-tenant vector. Redis session persistence/revocation was checked separately against live Redis.
- LLM integration: OpenAI-compatible provider supports environment credentials, configurable model, timeouts/retries, token usage and optional cost estimates. Mock provider tests pass; no live inference or streaming was run.
- Competitor intelligence: competitor sites use the existing crawler/indexer. Tenant-scoped coverage compares crawled topic phrases, displays match method, page counts and evidence links, and offers a cautious human-review action for competitor-only phrases. No search demand, rank, traffic, or backlink claims are made.

## Verified checks

- `cd backend && uv sync --extra dev` — passed.
- `cd backend && uv run pytest -q` — 60 passed, 3 opt-in PostgreSQL/Qdrant/audit integration tests skipped without service URLs; one Starlette/httpx deprecation warning. The PostgreSQL audit integration separately passed against a disposable PostgreSQL 16 database.
- `cd backend && uv run ruff check app tests` — passed.
- `cd backend && uv run mypy app` — passed (89 source files).
- `cd frontend && npm run lint`, `npm run typecheck`, and `npm run build` — passed.
- `cd frontend && npm audit` — passed; zero reported vulnerabilities.
- Browser workflow: loaded the live integration project, three persisted pages, completed crawl counters, and 27 audit findings after reload.
- SQLite and disposable PostgreSQL 16 Alembic upgrades — passed through `20261015_0003`.
- `cd frontend && npm run e2e:local` — 3 Playwright tests passed using local fixture services (SQLite/Redis/solo worker), including real Redis throttling, the pinned crawler transport, and competitor content-gap review; does not exercise PostgreSQL/Qdrant.
- Authenticated PostgreSQL/Qdrant integration — 2 passed against fresh PostgreSQL 16 and Qdrant 1.12.6, including vector-store and API-level isolation; migrations passed through `20261015_0003`, and test containers were removed. Redis sessions used the deterministic test double in this run.
- Controlled resolver tests — crawler connected to the approved loopback IP while preserving `Host`, and rejected a simulated public-to-private DNS answer before connecting.
- Controlled live workflow: readiness, Redis/Celery worker, PostgreSQL pages, Qdrant vectors, hybrid search, grounded mock RAG with citation, SEO audit, and cross-tenant `404` passed against a loopback fixture.
- A full isolated Linux/Python 3.12 Celery prefork workflow completed crawl, PostgreSQL persistence, Qdrant indexing, hybrid search, cited mock RAG, and SEO audit. macOS/Python 3.14 development uses the solo pool.

See [`docs/PROGRESS.md`](PROGRESS.md), [`docs/MVP_ROADMAP.md`](MVP_ROADMAP.md), and [`PROJECT_STATE.json`](../PROJECT_STATE.json) for the checkpoint and next work.


## 2026-10-15 auth update

- New clean local Git history begins at `e4cf581`; the original damaged Git metadata was preserved separately and not rewritten.
- Authentication and membership schema migrated in SQLite and PostgreSQL through `20261015_0003`; protected route, CSRF, PostgreSQL persistence, Redis logout revocation, and cross-tenant checks pass.
- The original damaged Git metadata remains preserved; commit `3d7db85` checkpoints the verified auth, provider, worker, browser, and competitor foundations in the clean local repository.
- Competitor evidence phrase coverage and browser flow are implemented. Semantic matching is wired to configured sentence-transformer embeddings; no real model quality evaluation has been run.
