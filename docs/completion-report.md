# Completion report — demonstration quality pass

## Summary

This pass makes the public storefront a credible demonstration: a sparse supplier row publishes as an accurate listing with a category-matching illustration, labeled corrections, inspectable evidence, and a server-enforced shopper cart. Stress-test fixtures stay off the shop grid.

## What changed

- Root `AGENTS.md` from the actual repository layout, commands, and symbols.
- Category-matching demonstration illustrations (`fixtures/demo_images/demo-*.png`), with source/usage/suitability tracking. They are labeled **not authentic product photography**.
- Public shop lists only curated demo SKUs (`app/services/demo_catalog.py`). CONFLICT / invalid-barcode / stress-test rows are not shown there.
- Sparse `HC-COKE-01` keeps a supplier price and, after barcode evidence fills title/brand, stale missing-field blockers are cleared so it can publish.
- Public provenance uses human-readable field labels. Shopper carts are cookie-scoped, isolated from verification carts, and use server prices/stock.
- Operator workspace hides stress-test and test-run batches unless **Show dev batches** is on.

## Tests run

```bash
cd services/api && .venv/bin/pytest -q   # 44 passed
cd apps/web && npx tsc --noEmit          # success
```

Browser checks against local `http://localhost:3000`: curated store grid (Bounty, Coca-Cola, Crest, Head & Shoulders, Tide) with matching illustrations; Coca-Cola PDP add-to-cart; preparation page showing empty title → Coca-Cola and replay evidence; cart with server price USD 5.99.

## Still unverified

- Live Bedrock structured output (no AWS credentials in this environment).
- Live UPCitemdb (no API key exercised).
- Hosted `https://shelfready.svgfy.com/store` still serves previously published data until that environment is redeployed.

## Demo sequence (replay)

1. Open `/store` — five household listings, category-matching demonstration images, no CONFLICT rows.
2. Open Coca-Cola → **See how this listing was prepared**: original empty title/brand, accepted corrections, replay barcode evidence.
3. **Add to cart** → cart count updates; `/store/cart` shows server price and stock.
4. Operator `/workspace` → **Try demo catalog** for conflicts and missing price; **Show dev batches** for the stress-test CSV.
