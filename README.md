# ShelfReady

**Tagline:** From messy supplier data to storefront-ready products.

ShelfReady is an AI product-onboarding agent for small e-commerce teams. It imports supplier catalogs, fixes safe inconsistencies, requests human decisions for ambiguous or consequential changes, publishes approved products to an **internal demo storefront**, and verifies that those products are purchasable.

This is a hackathon MVP for [Agents for Humans](https://agentsforhumans.devpost.com/). The agent uses the [Strands Agents SDK](https://strandsagents.com/) meaningfully; credentials stay server-side.

## Architecture

See [docs/architecture.md](docs/architecture.md).

```text
apps/web          Next.js operator UI + demo storefront
services/api      FastAPI, Strands agent, worker, SQLAlchemy/Alembic
packages/contracts  Shared notes (OpenAPI is source of truth)
fixtures          Synthetic supplier CSV, images, expectations
docs              Architecture, demo script, limitations, AgentCore guide
```

## Modes

| Mode | Env | Behavior |
|------|-----|----------|
| **Fixture replay** | `AGENT_MODE=replay` | Deterministic path through the same validation, decisions, publish, and verify services. **Visibly labeled** in the UI. No model calls. |
| **Live agent** | `AGENT_MODE=live` | Strands + Amazon Bedrock. Per product: inspect, optional lookup, structured `ProductAssessment`, then consume that assessment. |
| **Lookup** | `LOOKUP_PROVIDER=replay\|upcitemdb` | Independent of agent mode. A live agent with replay lookup is labeled **Live agent · replay lookup**. |

**Never** silently falls back from a failed live model call into replay mode. Live failures mark the job `failed`.

Operator writes go through the Next.js same-origin BFF. The API token is server-only (`API_TOKEN` / `SHELFREADY_API_TOKEN`). Do not set `NEXT_PUBLIC_API_TOKEN`. Published storefront reads, media, and listing provenance are public. Import, editing, and publication require operator access. Production API/worker require `ENVIRONMENT=production` and a non-localhost `DATABASE_URL`.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (PostgreSQL only)

## Quick start

```bash
# 1. Environment
cp .env.example .env
# Edit .env if needed. Default Postgres host port is 55433.

# 2. Database
docker compose up -d

# 3. API
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready
export SHELFREADY_API_TOKEN=dev-token-change-me
export AGENT_MODE=replay
export LOOKUP_PROVIDER=replay
export STORAGE_ROOT="$(pwd)/../../storage"
export FIXTURES_ROOT="$(pwd)/../../fixtures"
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

In a second terminal (worker):

```bash
cd services/api
source .venv/bin/activate
# same env exports as above
python -m app.worker
```

In a third terminal (web):

```bash
cd apps/web
# Browser calls same-origin /api. The Next.js server uses INTERNAL_API_URL + API_TOKEN.
export INTERNAL_API_URL=http://127.0.0.1:8000
export API_TOKEN=dev-token-change-me
npm install
npm run dev
```

Open http://localhost:3000 to browse the public demo store. Operator import and publishing live at `/workspace`. Seed publishes a small demonstration catalog when the store is empty.

## Live mode (Bedrock)

1. Set `AGENT_MODE=live` in `.env`.
2. Configure AWS credentials with Bedrock access for `BEDROCK_MODEL_ID` (default Claude Sonnet 4 on Bedrock).
3. Restart API and worker.
4. Confirm the UI badge shows **Live agent mode**.

## Tests

```bash
cd services/api
# with DATABASE_URL / FIXTURES_ROOT / STORAGE_ROOT / AGENT_MODE=replay set
pytest -q
```

Browser E2E (API + worker + web must be running):

```bash
cd apps/web
npx playwright install chromium
npx playwright test
```

## License

MIT — see [LICENSE](LICENSE).

## Disclosure

This repository is original work created for the Agents for Humans hackathon. It does not copy application code from other commerce projects. Fixture brands and images are synthetic.

## What is not claimed

- The demo storefront is **not** Shopify/Medusa and is **not** indexed for SEO ranking.
- Replay mode is **not** a live model integration.
- No public deployment is included; AgentCore steps are documented but not executed without authorization.
