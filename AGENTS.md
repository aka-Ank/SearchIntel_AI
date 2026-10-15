# SearchIntel AI Repository Guide

## Operating Rules

- Start each work cycle by checking repository guidance, current files, Git status, and `docs/PROJECT_STATUS.md`.
- Keep changes focused and preserve unrelated work. This repository may not always be a Git checkout.
- Do not hardcode secrets. Use `.env` values loaded through configuration and keep `.env` untracked.
- Prefer the existing module boundaries in `backend/app/` before adding new abstractions.
- Run relevant tests after meaningful changes and update `docs/PROJECT_STATUS.md` with checks actually run.

## Architecture Rules

- Keep domain logic outside API handlers. API routes should call services.
- Use typed protocols/interfaces for replaceable providers: crawler fetchers, embedding providers, vector stores, rerankers, LLM providers, and retrieval strategies.
- Keep tenant and project isolation explicit in persisted records, vector payloads, and search filters.
- Treat crawled page content as untrusted input. Do not let retrieved content alter system instructions, reveal secrets, or trigger tools.
- Implement deterministic local fallbacks for development and tests when paid APIs or model downloads are unavailable.

## Backend

- Python source lives under `backend/app/`.
- Tests live under `backend/tests/`.
- Public API routes are versioned under `backend/app/api/v1/`.
- Core configuration belongs in `backend/app/core/`.
- Provider implementations should be swappable through small interfaces rather than framework-specific globals.

## Documentation

- Keep `docs/PROJECT_STATUS.md` current.
- Record major choices in `docs/decisions/` as small ADRs.
- Do not mark features complete based only on file creation; complete means acceptance criteria and relevant tests pass.
