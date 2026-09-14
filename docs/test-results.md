# Test results

Run: 2026-09-14

## Backend (`services/api`)

```
pytest -q
38 passed
```

Includes: structured-output consumption, unknown/unrelated evidence rejection, stale revision rejection, listing-draft authenticity block, live orchestration with a controlled fake agent, truthful structured-output failure, decision resume targeting, publication idempotency, public storefront reads, production localhost config errors, plus existing identifiers/enrichment/decisions/integration/counts/policy/worker tests.

## Frontend (`apps/web`)

```
npx tsc --noEmit && npm run build
✓ Compiled successfully
```

## Live Bedrock

AWS credentials were not available in this environment. Live Bedrock invocation, real tool-call traces against Claude, and live structured_output from the hosted model remain unverified.

## Manual demo path (replay)

1. `POST /api/demo/load-demo` → import 10 demo products
2. Process job → enrichment evidence on UPC rows (predetermined in replay)
3. HC-COKE-02 → conflicting_variant decision visible
4. Resolve conflict / missing price → product fields update (replay does not enqueue a live resume)
5. Batch publish with selected product_ids → store + verification cart checks

Live UPCitemdb not run in CI (no API key). Live Bedrock not run (no AWS credentials).
