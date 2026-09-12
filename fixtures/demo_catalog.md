# Demo catalog scenarios

This file documents **deliberate demonstration inputs** in `demo_catalog.csv`. These are not real supplier mistakes.

| SKU | Scenario |
|-----|----------|
| HC-COKE-01 | Sparse row enriched from matching barcode evidence |
| HC-COKE-02 | Valid UPC with supplier color **Black** conflicting with record **Red** |
| HC-CREST-01 | Mostly complete; needs little intervention |
| HC-BAD-01 | Invalid check digit (`049000028910`) — no fabricated enrichment |
| HC-NOPRICE-01 | Missing required price — blocked until merchant enters price |
| HC-TIDE-01 | Complete Tide Pods row |
| HC-DEOD-01 | Missing barcode; brand+MPN search candidate (replay) |
| HC-TOWEL-01 | Normal household product |
| HC-SHAM-01 | Unsupported claim in description (sanitized) |
| HC-DUP-01 | Duplicate SKU with conflicting title/price |

Replay UPC fixtures live in `fixtures/replay/upc/`. Live lookups require `UPCITEMDB_API_KEY` and `LOOKUP_PROVIDER=upcitemdb`.
