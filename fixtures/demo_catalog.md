# Demo catalog scenarios

This file documents **deliberate demonstration inputs** in `demo_catalog.csv`. These are not real supplier mistakes.

| SKU | Scenario |
|-----|----------|
| HC-COKE-01 | Sparse title/brand enriched from matching barcode evidence; supplier price kept (public demo) |
| HC-COKE-02 | Valid UPC with supplier color **Black** conflicting with record **Red** (operator only) |
| HC-CREST-01 | Mostly complete; needs little intervention (public demo) |
| HC-BAD-01 | Invalid check digit (`049000028910`) — no fabricated enrichment (operator only) |
| HC-NOPRICE-01 | Missing required price — blocked until merchant enters price (operator only) |
| HC-TIDE-01 | Complete Tide Pods row (public demo) |
| HC-DEOD-01 | Missing barcode; brand+MPN search candidate (replay) (operator only) |
| HC-TOWEL-01 | Normal household product (public demo) |
| HC-SHAM-01 | Unsupported claim in description (sanitized) (public demo) |
| HC-DUP-01 | Duplicate SKU with conflicting title/price (operator only) |

Public storefront bootstrap publishes only the **public demo** SKUs, using category-matching demonstration illustrations in `fixtures/demo_images/` — not authentic product photography.

Replay UPC fixtures live in `fixtures/replay/upc/`. Live lookups require `UPCITEMDB_API_KEY` and `LOOKUP_PROVIDER=upcitemdb`.
