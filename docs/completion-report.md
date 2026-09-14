# Completion report — Seiko demonstration + missing-image recovery

## Summary

The featured public collection is a five-row Seiko 5 Sports supplier batch. SK-SRPD55-01 imports without an image; `retrieve_manufacturer_record` parses the official manufacturer page (replay HTML or network), stores the matching photograph with evidence, and publication uses the accepted asset. Household and stress-test fixtures are unchanged.

## Images downloaded (2026-09-14)

| File | Model page | Visual review |
|------|------------|---------------|
| SRPD55K1.png | SRPD55 | Black dial/bezel, steel bracelet |
| SRPD51K1.png | SRPD51 | Blue dial/bezel, steel bracelet |
| SRPD63K1.png | SRPD63 | Green dial/bezel, rose-gold hands |
| SRPD53K1.png | SRPD53 | Blue dial, blue/red bezel |
| SRPD55K1_1.jpg / _2.jpg | SRPD55 gallery | Lifestyle; not used as primary |

Suitability: source association on the official page plus manual review of the downloaded files. Not independent authentication. Usage: manufacturer-hosted; commercial republication not established; `demo_storefront_only` for this isolated demo.

The official SRPD55, SRPD51, SRPD63, and SRPD53 pages were re-opened on 2026-09-14 and still
identified those exact references and their matching catalog-image codes (`SRPD55K1`, `SRPD51K1`,
`SRPD63K1`, and `SRPD53K1`). Merchant fixture prices remain separate from Seiko's displayed price.

## Setup / reset

```
cd services/api && .venv/bin/alembic upgrade head
.venv/bin/python scripts/reset_seiko_demo.py          # dry-run
.venv/bin/python scripts/reset_seiko_demo.py --apply
.venv/bin/python scripts/build_seiko_handoff.py
```

Handoff zip: `artifacts/shelfready-seiko-image-handoff.zip`

The bundle contains six downloaded originals, six optimized derivatives, the contact sheet,
registry, JSON/CSV manifests, usage notes, and setup instructions. `unzip -t` reports no errors.

## Verification (2026-09-14)

- `cd services/api && .venv/bin/pytest -q` — 52 passed.
- `cd apps/web && npx tsc --noEmit && npm run build` — passed.
- `cd apps/web && PLAYWRIGHT_BASE_URL=http://localhost:3001 npx playwright test` — desktop
  Chrome and Pixel 7 projects passed. The flow checks the SRPD55 route, exact fixture price and
  stock, decoded product image, cart add feedback, quantity/totals, removal, empty state, and the
  public preparation-evidence page.
- `cd services/api && .venv/bin/python scripts/reset_seiko_demo.py --apply` — imported a fresh
  five-row batch; three eligible products published and all three passed adapter verification.
  The ambiguous-reference and wrong-variant scenarios were not featured.
- Public `GET /api/store/cart` is covered explicitly; it no longer falls through to the protected
  operator-cart route.

The first sandboxed test/build attempt could not reach local PostgreSQL or Google Fonts. Both were
rerun with the required local/network access and passed; those sandbox failures were environmental,
not counted as successful verification.

## Live blockers

- Live Bedrock structured output: requires AWS credentials / Bedrock. Not exercised if absent.
- Live manufacturer HTTP: used to download images for the bundle; runtime uses replay when `LOOKUP_PROVIDER=replay`.
- Manufacturer-hosted image publication rights were not independently established. The assets are
  labeled `demo_storefront_only`; they must not be represented as generally cleared commercial media.
