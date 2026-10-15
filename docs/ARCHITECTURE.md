# SearchIntel AI Architecture

## Product Boundary

SearchIntel AI is a multi-tenant platform for website crawling, semantic content understanding, hybrid retrieval, citation-based RAG, competitor intelligence, and SEO/GEO recommendations. The verified core MVP is the crawl-to-evidence vertical slice plus a connected local dashboard. The API and dashboard provide cookie-based authentication and tenant role checks. PostgreSQL auth migration, browser E2E, and initial competitor phrase coverage are verified; deeper production hardening remains in progress.

## System Components

### API Layer

FastAPI exposes versioned endpoints under `/api/v1`. API handlers validate requests and delegate work to services. They do not contain crawler, retrieval, NLP, graph, or scoring logic.

Endpoint groups:

- `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`
- `/api/v1/tenants` and `/api/v1/tenants/{tenant_id}/members`
- `/api/v1/health` (process liveness)
- `/api/v1/health/ready` (database, Redis, Celery worker readiness)
- `/api/v1/projects`
- `/api/v1/projects/{project_id}/websites`
- `/api/v1/projects/{project_id}/competitors/coverage`
- `/api/v1/websites/{website_id}/crawl`
- `/api/v1/websites/{website_id}/crawl-jobs` (tenant-scoped history)
- `/api/v1/crawl-jobs/{job_id}`
- `DELETE /api/v1/crawl-jobs/{job_id}`
- `/api/v1/websites/{website_id}/seo-audits`
- `GET /api/v1/websites/{website_id}/seo-audits` (tenant-scoped history)
- `/api/v1/seo-audits/{audit_run_id}` (findings, summary)
- `/api/v1/pages/{page_id}/seo-findings`
- `/api/v1/projects/{project_id}/pages`
- `/api/v1/pages/{page_id}`
- `/api/v1/search`
- `/api/v1/rag/query`
- legacy/local fixture indexing remains available at `/api/v1/index/url`
- planned: competitor SEO findings, recommendations, internal links, graph workflows, and broader dashboard views

### Frontend Dashboard

`frontend/` contains a Next.js App Router client dashboard using TypeScript and Tailwind CSS. It routes requests through a same-origin proxy to the versioned FastAPI API and reads persisted project, website, page, crawl, and audit data. It also submits hybrid-search and grounded-RAG questions and displays citations returned by the API. The dashboard uses FastAPI Users cookie sessions, restores the signed-in account, lists only authorized workspaces, and supplies a CSRF token on writes.

### Service Layer

Services coordinate implemented use cases:

- project creation
- crawl and index workflow
- asynchronous crawl and audit jobs
- deterministic SEO audits
- hybrid retrieval and grounded RAG
- planned: content gaps, internal link recommendations, and broader evaluation

Services accept explicit tenant and project context. Every content item and search filter carries tenant/project IDs. Competitor phrase coverage only uses successfully crawled project pages and includes source-page evidence.

Competitor coverage extracts bounded unigram, bigram, and trigram candidates from stored page titles and text. Exact phrase overlap is the offline default. When the configured provider is sentence-transformers, the service also embeds candidate phrases and treats cosine similarity at or above `0.82` as semantic overlap; each response identifies the match method and includes page evidence. This is a content-coverage signal, not a measure of search demand, rank, or traffic.

### Crawler

The crawler is split into:

- URL normalization and safety validation
- fetcher interface
- HTTP fetcher implementation
- HTML parser
- crawl orchestration

HTTP response bodies are read in bounded streaming mode, controlled by `CRAWLER_MAX_RESPONSE_BYTES` (5 MB by default, maximum 50 MB). Oversized content is treated as a failed page rather than retained fully in process memory.

The crawler supports bounded multi-page crawls with max-page and max-depth limits, same-host confinement, URL safety validation at each redirect, duplicate prevention, content-type filtering, configurable per-job concurrency, request pacing, and robots.txt restrictions. HTTP transient failures receive bounded exponential retries. Crawl jobs and audit runs are dispatched through Celery over Redis, with PostgreSQL as the job-state authority. Cancellation is cooperative between crawl batches and page indexing operations. Worker startup requeues pending and stale jobs. A pinned HTTPX/httpcore transport resolves and validates DNS answers immediately before opening the socket, connects to the vetted IP directly, and retains the requested hostname for HTTP `Host` and TLS SNI. Ambient proxy environment settings are disabled for crawler requests. Controlled tests cover an induced public-to-private DNS change; external crawling has not been performed as part of verification.

### Processing Pipeline

The processing pipeline converts HTML into normalized page content:

1. parse metadata, headings, links, and body text
2. clean boilerplate and non-content elements
3. chunk by document structure, not blind fixed character splitting
4. compute content hash
5. generate embeddings
6. index chunks into retrieval stores

### Retrieval

The retrieval stack has independent providers:

- dense vector search
- BM25 lexical search
- Reciprocal Rank Fusion
- reranker interface

The MVP keeps deterministic local embeddings so tests and demos do not require external keys or model downloads. A sentence-transformers provider supports local production use with `BAAI/bge-small-en-v1.5` by configuration. Qdrant is the production/default vector store when configured, and the in-memory vector store remains for fast offline tests. Cross-encoder reranking is available behind a `Reranker` interface, with `NoOpReranker` as the offline default.

### RAG

RAG uses retrieval results as explicitly untrusted content. Prompts separate system instructions from retrieved webpage text. Grounded mode answers only from supplied evidence and returns validated citations with URL, title, page ID, chunk ID, heading path, and snippet. The core implementation uses an `LLMProvider` abstraction with `MockLLMProvider` for offline tests and an optional OpenAI-compatible HTTP provider configured through environment settings. The real adapter has bounded timeouts/retries and returns token usage with an optional cost estimate. No real provider call or streaming response has been verified.

### Storage

The production persistence target is PostgreSQL with SQLAlchemy and Alembic for relational entities:

- Tenant
- Project
- Website
- Competitor
- Page
- PageSnapshot
- ContentChunk
- Entity
- Topic
- Link
- Keyword
- CrawlJob
- AnalysisJob
- RAGQuery
- RetrievedChunk
- EvaluationResult

PostgreSQL stores projects, websites, pages, chunks, crawl jobs, SEO audit runs, and findings through SQLAlchemy and Alembic migrations. Qdrant stores chunk vectors with payload filters for tenant, project, website, and page IDs. Redis is the Celery broker and result backend. Neo4j is reserved for graph queries once the crawl/content model is stable.

### Multi-Tenancy

Tenant membership rows bind registered users to tenants with owner, admin, editor, or viewer roles. Protected API routes check membership and minimum role before service access. Cookie writes use a strict SameSite session cookie plus CSRF double-submit validation. Opaque session tokens are stored in Redis and deleted on logout. Redis Lua counters rate-limit login, registration, crawl enqueue, and audit enqueue by immediate peer address and operation category; trust of forwarded headers is intentionally not enabled. PostgreSQL auth migration, session revocation, cross-tenant access, and real-Redis throttling were verified. A fresh Qdrant integration also verified tenant payload filters when tenants shared project and website identifiers. The full auth-to-Qdrant request path remains to be verified.

Tenant isolation is enforced at every boundary:

- API requests include tenant context.
- Database rows include tenant ID and project ID where applicable.
- Vector payloads include tenant/project filters.
- Retrieval services always filter by tenant/project.
- Tests prove tenant A cannot retrieve tenant B content.

### Observability

Structured logs include request ID, tenant ID, project ID, crawl job ID, and timing for crawling, embedding, retrieval, reranking, and LLM calls. Secret values must never be logged.

`/api/v1/health/ready` performs bounded checks for database connectivity, Redis broker reachability, and at least one responding Celery worker. It returns `503` when any dependency is unavailable; liveness remains separately exposed at `/api/v1/health`.

## Persistent Crawl-To-Search Flow

```text
Website
  -> bounded crawler
  -> parser / content normalization
  -> PostgreSQL Page
  -> structure-aware chunks
  -> PostgreSQL ContentChunk
  -> embedding provider
  -> Qdrant point payloads

Query
  -> query processor
  -> BM25 rebuilt from persisted chunks
  -> Qdrant dense retrieval with embedding-version filters
  -> Reciprocal Rank Fusion
  -> optional cross-encoder reranker
  -> source URL / chunk search results
```

If a page content hash is unchanged, the pipeline updates crawl metadata but skips chunk replacement, embedding, and vector replacement.

Embedding model changes are handled by versioned Qdrant collection names plus embedding metadata in point payloads. The maintenance CLI can reindex persisted chunks into the currently configured vector collection.

## Grounded RAG Flow

```text
Question
  -> retrieval strategy: bm25 | dense | hybrid | hybrid_rerank
  -> context builder with stable citation numbers
  -> grounded prompt
  -> LLM provider
  -> citation validation / repair
  -> structured answer with citations
```

Retrieved webpage text is treated as untrusted evidence, not instructions.

## First Vertical Slice

The first production slice is:

```text
Website URL
  -> safe URL validation
  -> fetch HTML
  -> parse page metadata and text
  -> structure-aware chunks
  -> deterministic embedding provider
  -> vector and BM25 indexes
  -> hybrid search API
  -> retrieved results with source metadata
```

This flow has passed unit checks and a controlled PostgreSQL/Redis/Celery/Qdrant integration against a loopback fixture. Deterministic embeddings and a mock LLM remain the offline defaults; external model quality and production deployment are not verified.

## MVP Milestones

1. Local crawl-to-search/RAG foundation — implemented and regression-tested.
2. PostgreSQL models and Alembic migrations — SQLite and isolated PostgreSQL migrations pass.
3. Bounded asynchronous crawl and deterministic SEO audits — unit-tested and controlled live worker verified with Celery solo pool.
4. Qdrant hybrid retrieval and grounded RAG — controlled service workflow verified; mock LLM only.
5. Connected Next.js dashboard — build- and browser-verified against live local APIs.
6. Production hardening — full Linux/Python 3.12 prefork crawl, authenticated tenant identity, browser E2E, retry/recovery tests, PostgreSQL auth checks, Redis-backed API rate limits, controlled DNS pinning checks, and isolated Qdrant tenant filtering pass. Reviewed legacy membership backfill, authenticated API-to-Qdrant verification, broader fault injection, and performance profiling remain pending.
7. Advanced product work — initial competitor phrase coverage is implemented with optional configured sentence-transformer similarity. Deeper competitor SEO, recommendations, monitoring, graph/agent workflows, GEO, integrations, deployment, and reproducible research remain planned.

## Async Crawl and SEO Audit Worker

The API persists a crawl or audit run before dispatching the Celery task. The worker reconstructs the service container and writes progress to PostgreSQL. A partial unique index prevents multiple active crawl jobs for one tenant/project/website. Crawls persist individual pages and chunks through the existing indexing service, which skips vector/chunk replacement when the content hash is unchanged. A worker startup recovery task requeues pending and stale running jobs. Audit results are relational records with tenant scope and evidence; the deterministic audit engine labels indexability as unverified unless an external search provider is later integrated.

Run a worker locally from `backend/` with `uv run celery -A app.tasks.queue:celery_app worker --loglevel=INFO --queues=crawls,audits --pool=solo --concurrency=1`. This requires reachable Redis and PostgreSQL. The full crawl/search/RAG/audit workflow passed on both the host's solo pool and Linux/Python 3.12 prefork. The host's Python 3.14/macOS prefork tracer previously crashed, so the local fallback remains solo. Recovery tasks are routed to the crawl queue consumed by the documented worker command.

## Key Tradeoffs

- Local deterministic providers first: this keeps development reproducible and testable without external credentials, but it is not the final retrieval quality target.
- Direct retrieval implementation: BM25, fusion, and provider contracts are implemented directly so the system is interview-defensible and not hidden behind a broad orchestration framework.
- LangGraph later: workflow orchestration is useful for the SEO Analyst agent, but premature until retrieval, evidence models, and citation validation are stable.
- Neo4j later: graph storage adds operational cost, so the MVP first proves content extraction, entity/topic generation, and link relationships.
