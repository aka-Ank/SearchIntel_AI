# Recovery report

Date: 2026-10-15

## Recovery result

- The archived SearchIntel source is at `/Users/aka_ank/iCloud Drive (Archive) - 1/Desktop/SEO` and remains unchanged.
- All 66 regular files from that archive are now present in this workspace. They matched the archive immediately after copying; `.env.example`, `docker-compose.yml`, and `README.md` were then intentionally edited to remove sample passwords and require local environment values. Existing workspace files were preserved; missing archive files were copied only into absent paths.
- The recovered source passes 27 tests, Ruff, and mypy. These are current checks on the restored workspace, not claims about the archive's former runtime services.
- The archive does not contain the Next.js frontend or the earlier recovery/MVP tracking artifacts. A search of nearby Desktop/Documents and Codex files found no second copy of those files. The required recovery/progress/roadmap/state files have been recreated from verified current findings; the missing frontend and later background-crawl/SEO implementation have not been represented as restored.
- Docker-backed services have not been started; the Docker daemon was unavailable at the last check.

## Git state

- The current workspace has one local commit, `e6265dacfc9550de62cc501315f7670db7fd6a31` (`feat: initial SearchIntel AI vertical slice`), but `git fsck` reports missing objects referenced by its tree. No remote is configured.
- Archived source files were restored in the working tree and staged to clear their deletion state. No commit was created. The local `.claude/settings.local.json` was left untouched and excluded from staging.

## Known missing work beyond the archive

The archive is the latest complete source copy found. It predates the dashboard and the later crawl-worker/technical-audit implementation previously reported in this conversation. Those newer files were absent from the workspace, archive, and nearby local searches; they cannot be claimed as recovered from this backup.
