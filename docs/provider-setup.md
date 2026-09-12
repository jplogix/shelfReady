# UPC lookup provider setup

ShelfReady supports **one** barcode enrichment provider in this pass: [UPCitemdb](https://devs.upcitemdb.com/docs).

## Modes

| Setting | Behavior |
|---------|----------|
| `LOOKUP_PROVIDER=replay` | Uses labeled fixtures in `fixtures/replay/upc/*.json`. No HTTP calls. |
| `LOOKUP_PROVIDER=upcitemdb` | Live HTTP lookups when `UPCITEMDB_API_KEY` is set. |

**Important:** A failed live lookup is recorded as `lookup_unavailable`. The system **never** silently substitutes replay fixtures when live mode fails.

## Environment variables

```env
LOOKUP_PROVIDER=replay          # replay | upcitemdb
UPCITEMDB_API_KEY=              # server-only; never expose to the web app
LOOKUP_BUDGET_PER_RUN=25
LOOKUP_TIMEOUT_SECONDS=10
LOOKUP_MAX_RETRIES=2
```

## Live trial setup

1. Register for a UPCitemdb developer key (trial/experimental plan).
2. Set `UPCITEMDB_API_KEY` in `.env` (API service only).
3. Set `LOOKUP_PROVIDER=upcitemdb`.
4. Restart the API and worker.
5. Load **`Try demo catalog`** — rows include real UPCs validated in replay fixtures.

Rate limits and quotas are enforced with caching, deduplication, and a per-run budget.

## Replay demo (no key required)

1. Keep `LOOKUP_PROVIDER=replay` (default in `.env.example`).
2. Run API + worker + web.
3. Home → **Try demo catalog** → **Prepare products**.
4. Evidence rows are labeled **replay fixture** in the product drawer.

## Datasets

| File | Purpose |
|------|---------|
| `fixtures/supplier_catalog.csv` | Synthetic stress-test (no real barcodes) |
| `fixtures/demo_catalog.csv` | 10 household demo rows with real UPCs |
| `fixtures/demo_catalog.md` | Documented deliberate corruptions |

## What remains unverified without live key

- Actual UPCitemdb HTTP latency, quota behavior, and response shape drift
- Live search-by-brand+MPN coverage for sparse rows

Replay fixtures verify matching, conflicts, invalid identifiers, and evidence persistence.
