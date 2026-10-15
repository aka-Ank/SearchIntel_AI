# SearchIntel AI MVP roadmap

## Stage 0 — Recovery

**Complete.** Restored and verified the available archived source. The archive remains unchanged. Git history has missing objects and no configured remote.

## Stage 1 — Baseline verification

**Local and controlled service verification complete.** 40 backend tests, Ruff, mypy, and migrations through `20261015_0002` pass. A fresh isolated Docker Compose stack ran PostgreSQL, Redis, and Qdrant; the existing `seo-*` stack and data volumes were preserved.

## Stage 2 — Background crawl infrastructure

**Implemented; unit and controlled service verification passed.** Redis-backed Celery tasks create and execute persistent PostgreSQL jobs, track progress, handle duplicate active jobs, support cancellation, retry transient HTTP failures with bounded exponential backoff, and requeue stale work on worker startup. Live recovery requeued and completed a persisted pending crawl. Existing page/chunk persistence and content-hash skip behavior remain in place. A loopback fixture crawl persisted three pages and indexed three Qdrant vectors. The local verification worker needed Celery's solo pool because prefork failed inside its task tracer on Python 3.14/macOS; prefork remains unverified on the target production runtime.

## Stage 3 — Technical SEO engine

**Implemented; unit and controlled service verification passed.** Deterministic findings cover HTTP status, title/description presence/length/duplication, headings, canonical signals, robots/noindex, link counts and verified broken internal links, thin/exact/near-duplicate content, image alt text, sitemap XML, and JSON-LD syntax. Relational audit runs/findings and tenant-scoped status, history, findings, filtering, summary, and page-specific endpoints are implemented. A live worker audited three persisted fixture pages and stored 27 findings.

## Stage 4 — Frontend dashboard

**Core dashboard implemented and browser-verified against live local services.** Next.js 16, React 19, TypeScript, Tailwind CSS 4, and Biome lint are configured. The dashboard calls project, website, page, crawl, audit, search, and RAG APIs and provides creation, status, progress, filtering, cancellation, empty, loading, and error states. Tenant selection is stored in browser storage; latest crawl, audit history, and findings load from persisted APIs. Production build, typecheck, lint, and dependency audit pass. The browser displayed three persisted pages, completed crawl counters, and all 27 SEO findings from the live service run.

## Stage 5 — End-to-end validation

**Controlled local workflow verified; production-runtime coverage pending.** A fresh PostgreSQL/Redis/Qdrant stack, live Celery solo worker, FastAPI, and loopback fixture completed crawl → PostgreSQL persistence → Qdrant indexing → hybrid search → grounded mock RAG → SEO audit. Readiness reported healthy and cross-tenant lookup returned 404. Prefork, transient task retry, cancellation, load behavior, and production authentication have not been verified end to end.

## Reliability hardening checkpoint

**Response-size bounds implemented and locally tested.** HTTP bodies are consumed incrementally and rejected after a configurable maximum (5 MB default, 50 MB configuration ceiling); this prevents an unusually large page or robots file from being fully buffered. It does not yet pin DNS resolution to a validated IP, so DNS rebinding protection remains a production security task.

`GET /api/v1/health/ready` checks SQL persistence, Redis reachability, and Celery worker responses with bounded network timeouts. Unit tests cover ready and no-worker states; the live check returned ready against the isolated services and worker.

## Advanced phases

Competitor comparison, recommendations, monitoring/reporting, graph intelligence, agentic workflows, GEO analysis, search-data integrations, broader security/performance, production deployment, and reproducible research experiments remain pending. Track actual implementation and external authorization separately; do not represent these as completed.

## Security and verification constraints

- No external crawl is run as part of the automated test suite; fixtures and mocked fetchers are used.
- Private-network destinations, unsafe schemes, unsafe redirects, and cross-host crawl redirects are rejected by the configured crawl policy.
- Crawled content remains untrusted evidence; tenant and project filters are persisted in relational and vector paths.
- No paid LLM or search-console API has been called. Live model/provider verification requires configured credentials and authorization.
- Do not claim Docker-backed service behavior until those services and workflows have actually run.
