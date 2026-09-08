# Observed test results

Recorded during local MVP implementation (replay mode). Do not invent additional metrics.

## Pytest (`services/api`)

Command:

```bash
cd services/api
DATABASE_URL=postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready \
SHELFREADY_API_TOKEN=dev-token-change-me \
AGENT_MODE=replay \
STORAGE_ROOT=<repo>/storage \
FIXTURES_ROOT=<repo>/fixtures \
.venv/bin/pytest -q
```

Observed: **17 passed** (unit, integration, worker recovery).

## Playwright (`apps/web`)

Requires API + worker + Next.js. Default Playwright `baseURL` is `http://localhost:3001` (set `PLAYWRIGHT_BASE_URL` if needed).

```bash
cd apps/web
npx playwright test --project=desktop
npx playwright test --project=mobile
```

Observed:

- desktop: **1 passed** (vertical slice ~16s)
- mobile: **1 passed** (vertical slice ~11s)
