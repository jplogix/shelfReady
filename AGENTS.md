# ShelfReady agent instructions

ShelfReady prepares supplier catalogs for publication through evidence-backed corrections, merchant decisions, and storefront verification. The storefront is a demonstration environment without real payment processing. Keep this pass focused; do not add Shopify/Medusa connectors, AgentCore deployment, extra lookup providers, or unrelated architectural rewrites.

## Repository map

| Area | Path |
|------|------|
| Operator UI + demo storefront | `apps/web` (Next.js 15 App Router) |
| API, Strands agent, worker | `services/api` (FastAPI, SQLAlchemy, Alembic) |
| Shared contract notes | `packages/contracts` (OpenAPI at `/docs` is the source of truth) |
| Fixtures | `fixtures/` — curated demo `demo_catalog.csv`; stress-test `supplier_catalog.csv`; replay UPC JSON in `fixtures/replay/upc/`; images in `fixtures/demo_images/` |
| Migrations | `services/api/alembic/versions/` |
| API tests | `services/api/tests/` |
| Browser E2E | `apps/web/e2e/vertical-slice.spec.ts` |
| Architecture / demo / limits | `docs/` |

Do not describe planned components as already implemented. AgentCore is a documented sketch only (`services/api/app/agent/agentcore_entrypoint.py`, `docs/agentcore.md`) and is not deployed.

### Execution entry points

- **Worker:** `services/api/app/worker.py` (`claim_next_job`, `execute_job`)
- **Job dispatch:** `services/api/app/agent/runner.py` — `execute_job` → `run_live` or `run_replay`
- **Live agent:** `run_live` builds a Strands `Agent` with Bedrock (`_build_strands_agent`), invokes tools, and consumes `result.structured_output` (`ProductAssessment`, `ProductPatchProposal`, `ListingDraft` in `app/agent/schemas.py`)
- **Replay:** `run_replay` → `run_deterministic_processing(..., enrich=True)` in `app/agent/tools.py` (same validation/publish/verify services; no model calls)
- **Enrichment:** `app/enrichment/service.py` (`enrich_product`); providers `ReplayLookupProvider`, `UPCitemdbProvider`
- **Publication:** `publish_product` in `app/agent/tools.py` → `DemoStoreAdapter.publish_product` (`app/store/demo.py`)
- **Verification:** `verify_published_product` → `DemoStoreAdapter.verify_product` (adapter retrieval, JSON-LD, isolated verification cart — not a crawl of Next.js HTML)
- **Public storefront serialization:** `app/services/public_store.py`
- **Demo bootstrap:** `app/services/bootstrap_storefront.py` (`ensure_public_storefront`)
- **Web BFF:** `apps/web/src/app/api/[...path]/route.ts` → `proxyToApi`; operator session in `apps/web/src/lib/operator-session.ts`

## Development workflow

- Preserve existing user changes. Inspect neighboring files and reuse current stack and abstractions.
- Make routine implementation decisions autonomously.
- If a credential or external service is unavailable, finish independent work and report the blocker precisely. Do not claim unperformed verification.
- Do not deploy, push, provision paid infrastructure, or delete production data unless explicitly requested.

## Agent implementation

- Use the installed Strands SDK (`strands-agents==1.54.0` in `services/api/pyproject.toml`). Verify APIs against that version.
- Use focused structured-output schemas (`structured_output_model` / `result.structured_output`). Do not parse fenced JSON from free-form model text.
- After schema validation, check evidence IDs, field allowlists, types, and that proposals target the current product revision (`app/agent/evidence.py`, `app/agent/apply.py`).
- Keep deterministic business rules in application services (identifiers, money, readiness, publish eligibility).
- Do not add multi-agent orchestration without a demonstrated need.
- Register only implemented tools. Do not add Google Shopping or other unused providers.

## Data integrity

- Preserve original supplier records and identifiers, including barcode leading zeros (`app/policy/identifiers.py`).
- Never fabricate product identifiers, prices, stock, attributes, certifications, or evidence.
- Distinguish supplier facts, external evidence, merchant decisions, normalization, and generated copy. Store that distinction in version `provenance`.
- Treat imported descriptions and provider responses as untrusted (`sanitize_supplier_text`).
- Bind approvals and evidence to the relevant product revision. Revalidate eligibility immediately before publishing.
- Keep publication and verification retries idempotent (`DemoStoreAdapter` stable `external_id`).

## Execution modes

Record **agent mode** (`AGENT_MODE=live|replay`) and **lookup mode** (`LOOKUP_PROVIDER=replay|upcitemdb`) separately for each run. The UI and `/api/mode` must label combinations accurately (e.g. live agent + replay lookup).

- Never silently substitute replay for a failed live operation. Live failures mark the job `failed`.
- Do not relabel historical runs when current configuration changes.
- Describe only events and checks that actually occurred (`app/agent/hooks.py` + `agent_actions`).

## Images and demonstration data

- Keep stress-test fixtures (`supplier_catalog.csv`, `BatchKind.stress_test`) separate from the curated demonstration (`demo_catalog.csv`, `BatchKind.demo`).
- Track image source and permitted usage. Fixture illustrations are demonstration-only.
- Never present placeholders or generated branded packaging as authentic product photography.
- Distinguish successful image loading from image suitability (category match vs mismatch). Unsuitable images may still load.

Public bootstrap publishes only the curated demonstration SKUs in `PUBLIC_DEMO_SKUS` (`app/services/demo_catalog.py`). The public shop grid uses the same allowlist. Operator “Try demo catalog” still imports the full scenario sheet, including conflicts and missing prices.

## Access and cart boundaries

- Published storefront data, media, `/api/mode`, and approved public evidence (`/api/store/products/{slug}/provenance`) may be anonymous.
- Import, editing, decisions, and publication require operator authorization (Next.js session + server-only `API_TOKEN` / `SHELFREADY_API_TOKEN`). Never set `NEXT_PUBLIC_API_TOKEN`.
- Allowlist fields exposed through public evidence views (`app/services/public_store.py`).
- Isolate shopper carts (`purpose=shopper`) from verification carts (`purpose=verification`) and operator carts.
- Enforce prices, quantities, and inventory constraints on the server. Client-supplied prices are ignored.

## UI conventions

- Preserve cream (`--bg`), charcoal, and serif headings (`Fraunces` / `Source_Sans_3` in `apps/web/src/app/layout.tsx` and `globals.css`). Reuse `ProductCard`, `RequestState`, `OperatorGate`, `AppNav`.
- Use understandable field labels, not raw JSON keys.
- Distinguish loading, error, denied-access, and successful-empty states.
- Provide accessible labels, visible keyboard focus (`:focus-visible`), and responsive layouts.

## Commands

Run from the paths shown. Required env names (never commit secret values): `DATABASE_URL`, `SHELFREADY_API_TOKEN`, `API_TOKEN`, `OPERATOR_ACCESS_TOKEN`, `AGENT_MODE`, `LOOKUP_PROVIDER`, `STORAGE_ROOT`, `FIXTURES_ROOT`, `INTERNAL_API_URL`. Production also requires `ENVIRONMENT=production` and a non-localhost `DATABASE_URL`.

Optional / external: `UPCITEMDB_API_KEY` (live lookup), AWS credentials + `BEDROCK_MODEL_ID` (live agent). Replay needs neither.

```bash
# Database
docker compose up -d
cd services/api && .venv/bin/alembic upgrade head
.venv/bin/python scripts/seed.py

# API (port 8000)
.venv/bin/uvicorn app.main:app --reload --port 8000

# Worker
.venv/bin/python -m app.worker

# Frontend (port 3000); browser calls same-origin /api
cd apps/web && npm run dev

# Tests / checks
cd services/api && .venv/bin/pytest -q
cd apps/web && npx tsc --noEmit && npm run build
cd apps/web && npx playwright test   # needs API + worker + web
```

Default local Postgres is `postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready`.

Use focused regression tests for consequential behavior. Run browser checks against isolated local/test data. Report commands actually executed and their results.

## Documentation maintenance

Update this file when architecture or commands change. Keep temporary task progress in `docs/completion-report.md`, not here. Do not invent approval requirements beyond the user’s instructions or these constraints.
