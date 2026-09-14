# Five-minute demo script

**Setup:** `AGENT_MODE=replay`, `LOOKUP_PROVIDER=replay`, API + worker + web running. UI shows **Fixture replay mode**.

1. **Problem (30s)** — Small stores spend hours cleaning supplier spreadsheets. ShelfReady imports, enriches from barcode evidence, escalates conflicts, publishes, and verifies — not a chatbot that only recommends.

2. **Try demo catalog (30s)** — Operator workspace → **Try demo catalog**. Show household rows with real UPCs and documented demo scenarios (`fixtures/demo_catalog.md`). The public shop at `/store` shows only the curated, published listings.

3. **Prepare products (45s)** — **Prepare products**. Open **Run activity** — tool actions include `lookup_product_identifier`. Batch summary shows ready / needs information / conflicts.

4. **Workbench (60s)** — Open **HC-COKE-01**: sparse supplier title/brand enriched from replay barcode evidence (labeled **replay fixture**), with a soda-can demonstration illustration. Open **HC-COKE-02**: “Supplier says Black. The barcode record says Red.” Resolve the variant conflict in the drawer.

5. **Missing price (30s)** — **HC-NOPRICE-01**: enter price in drawer (no “Approve null” path).

6. **Publish + verify (60s)** — Select ready products → **Review and publish**. Open demo store product link from drawer. Show verification count on batch summary.

7. **Stress test (optional, dev view)** — **Show dev batches** → load stress-test catalog for alias/duplicate/injection cases.

8. **Close (30s)** — Live mode uses Strands structured assessments plus tools; replay never pretends to be live. A live model with replay lookup is labeled **Live agent · replay lookup**. Live UPC lookups require `UPCITEMDB_API_KEY` (`docs/provider-setup.md`).

**Use only counts visible on screen — do not invent accuracy % or time saved.**
