# Test results

Run: 2026-03-22

## Backend (`services/api`)

```
pytest -q
23 passed
```

Includes: identifiers, enrichment, decisions (approve-null), integration E2E, counts, policy, worker recovery.

## Frontend (`apps/web`)

```
npm run build
✓ Compiled successfully
```

## Manual demo path (replay)

1. `POST /api/demo/load-demo` → import 10 demo products
2. Process job → enrichment evidence on UPC rows
3. HC-COKE-02 → conflicting_variant decision visible
4. Batch publish with selected product_ids → store + verification

Live UPCitemdb not run in CI (no API key).
