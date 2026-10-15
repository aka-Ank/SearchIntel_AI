# SearchIntel AI MVP roadmap

## Stage 0 — Recovery

**Complete.** Restored and verified the available archived source. The archive remains unchanged. Git history has missing objects and no configured remote.

## Stage 1 — Baseline verification

**Local and controlled service verification complete.** 53 backend tests, Ruff, mypy, frontend lint/typecheck/build, and SQLite/PostgreSQL migrations through `20261015_0003` pass. A controlled Docker stack has run PostgreSQL, Redis, and Qdrant.

## Stage 2 — Background crawl infrastructure

**Implemented; service, solo, and Linux prefork verification passed.** Redis-backed Celery tasks create and execute persistent PostgreSQL jobs, track progress, handle duplicate active jobs, support cancellation, retry transient HTTP failures with bounded exponential backoff, and requeue stale work on worker startup. Live recovery requeued and completed a persisted pending crawl. A full Python 3.12 prefork workflow crawled two fixture pages, persisted PostgreSQL pages and chunks, indexed Qdrant vectors, returned hybrid-search results and a cited mock RAG response, and completed a technical audit. The documented macOS/Python 3.14 development fallback remains the solo pool.

## Stage 3 — Technical SEO engine

**Implemented; unit and controlled service verification passed.** Deterministic findings cover HTTP status, title/description presence/length/duplication, headings, canonical signals, robots/noindex, link counts and verified broken internal links, thin/exact/near-duplicate content, image alt text, sitemap XML, and JSON-LD syntax. Relational audit runs/findings and tenant-scoped status, history, findings, filtering, summary, and page-specific endpoints are implemented. A live worker audited three persisted fixture pages and stored 27 findings.

## Stage 4 — Frontend dashboard

**Dashboard implemented and browser E2E verified.** Next.js 16, React 19, TypeScript, Tailwind CSS 4, and Biome are configured. Playwright tests pass against real local APIs and worker; they cover auth, project/site registration, crawl, audit, pages, cited mock RAG, competitor crawl/coverage, tenant denial, and API failure UI. Production build, typecheck, lint, and dependency audit pass.

## Stage 5 — End-to-end validation

**Controlled local workflow verified with Celery solo and prefork.** Isolated PostgreSQL/Redis/Qdrant stacks completed crawl → PostgreSQL persistence → Qdrant indexing → hybrid search → grounded mock RAG → SEO audit. The prefork run used Linux/Python 3.12. PostgreSQL auth/session and tenant-isolation checks also passed separately. Playwright passed against SQLite, Redis, solo Celery, FastAPI, and Next.js.

## Reliability hardening checkpoint

**Response-size bounds implemented and locally tested.** HTTP bodies are consumed incrementally and rejected after a configurable maximum (5 MB default, 50 MB configuration ceiling); this prevents an unusually large page or robots file from being fully buffered. It does not yet pin DNS resolution to a validated IP, so DNS rebinding protection remains a production security task.

`GET /api/v1/health/ready` checks SQL persistence, Redis reachability, and Celery worker responses with bounded network timeouts. Unit tests cover ready and no-worker states; the live check returned ready against the isolated services and worker.

## Advanced phases

Initial competitor registration, crawl/indexing, evidence-linked phrase coverage, and dashboard display are implemented. When sentence-transformers is configured, coverage can use semantic similarity; the default deterministic embedding mode compares exact phrases only. Search ranking/traffic/backlinks, deeper competitor audits, recommendations, monitoring/reporting, graph intelligence, agentic workflows, GEO analysis, search-data integrations, broader security/performance, production deployment, and reproducible research experiments remain pending.

## Security and verification constraints

- No external crawl is run as part of the automated test suite; fixtures and mocked fetchers are used.
- Private-network destinations, unsafe schemes, unsafe redirects, and cross-host crawl redirects are rejected by the configured crawl policy.
- Crawled content remains untrusted evidence; tenant and project filters are persisted in relational and vector paths.
- No paid LLM or search-console API has been called. Live model/provider verification requires configured credentials and authorization.
- Do not claim Docker-backed service behavior until those services and workflows have actually run.


## Stage 6 — Authentication and tenant roles

**Implemented and verified locally with SQLite, PostgreSQL, Redis, and browser E2E.** FastAPI Users provides registration, password hashing, opaque Redis-backed cookie sessions, logout revocation, and current-user lookup. Alembic `20261015_0003` adds users and tenant memberships. Owner/admin member routes grant viewer/editor/admin roles to registered users. Cookie writes require CSRF. Protected routes enforce tenant membership and minimum roles. The 53-test suite, Ruff, mypy, frontend checks, SQLite/PostgreSQL migrations, PostgreSQL cross-tenant checks, Redis logout replay rejection, browser auth flows, and Redis-backed API throttling pass. Legacy membership backfill remains open.

## Stage 7 — Worker reliability and configured LLM adapter

**Implemented with deterministic tests and full runtime verification.** Worker tests cover transient retry, stale-job recovery, cancellation/idempotency state, and durable failure reporting. The Linux/Python 3.12 prefork workflow completed crawl through audit against isolated PostgreSQL/Redis/Qdrant. The OpenAI-compatible LLM adapter supports environment credentials, timeouts, bounded retries, token usage, optional cost estimates, evidence-grounded prompts, and citation checks. Mock tests pass; live-provider smoke and streaming remain unverified.

## Stage 8 — Competitor coverage foundation

**Initial implementation and browser flow verified.** Competitor websites can be registered, crawled and indexed through the existing worker. The tenant-scoped coverage endpoint compares extracted phrases and links every candidate to crawled-page evidence. Configured sentence-transformers embeddings enable semantic phrase matching; the deterministic default only compares exact phrases. The UI does not claim demand, traffic, rankings, or backlinks. Advanced competitor SEO analysis and recommendations remain open.

## Next stages

- Expand worker fault/load testing and verify throttling behind the intended trusted-proxy configuration.
- Plan an explicit legacy membership backfill and close the crawler DNS rebinding gap.
- Add provider streaming and run a real-provider smoke only when credentials and explicit paid-inference authorization exist; retain mock CI.
- Improve semantic competitor analysis quality, then add comparative SEO findings and recommendations without asserting unavailable search metrics.
- Continue recommendations, monitoring, graph, GEO, authorized search analytics, performance, deployment, and research phases from the master roadmap.
