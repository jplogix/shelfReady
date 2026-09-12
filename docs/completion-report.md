# Completion report — ShelfReady hackathon pass

## Summary

This pass delivers a convincing vertical slice: barcode enrichment with field-level evidence, a product-centric batch workbench, batch publication approval (no per-product publication cards), and storefront verification — while preserving the existing Strands/replay/live stack and synthetic stress-test fixture.

## What changed

### Backend
- Migration `0003_enrichment_evidence`: `field_evidence`, `lookup_cache`, product `readiness`/`supplier_sku`/`store_slug`, batch `batch_kind`, new decision kinds
- CSV import: optional `gtin`, `upc`, `ean`, `mpn`, `model`, `size`, `pack_quantity` (leading zeros preserved)
- `app/enrichment/`: UPCitemdb adapter, replay fixtures, compare/match logic, budget/cache/dedup
- Strands tool `lookup_product_identifier`; deterministic enrichment during processing
- Removed auto-generated **publication** decision cards; batch publish binds `approved_version_id` per selected product revision
- Approve-null guard for missing required values
- Batch counts: ready / needs information / conflicts / published / verified / issues

### Frontend
- Batch workbench (~1400px): summary, filters, search, product table with enrichment summary
- Product drawer: supplier record, evidence & decisions, storefront preview
- Landing: **Try demo catalog**, dev stress-test toggle, meaningful batch names

### Data
- `fixtures/demo_catalog.csv` + replay UPC JSON + `fixtures/demo_catalog.md`
- `fixtures/supplier_catalog.csv` unchanged

## Tests run

```bash
cd services/api && pytest -q   # 23 passed
cd apps/web && npm run build   # success
```

New tests: `test_identifiers.py`, `test_enrichment.py`, `test_decisions.py`; updated `test_integration.py`.

## Demo script (replay)

1. Home → **Try demo catalog**
2. Batch → **Prepare products** → open **HC-COKE-01** (sparse → enriched evidence) and **HC-COKE-02** (color conflict)
3. Resolve conflict in drawer; enter price for **HC-NOPRICE-01**
4. Select ready products → **Review and publish**
5. Open demo store links; verify published + verification counts on batch summary

Use on-screen counts only.

## Limitations

- Single UPC provider (UPCitemdb); no Shopify connector
- Live UPCitemdb not exercised in CI (replay fixtures used)
- Demo images reuse bundled fixture assets (not provider images)
- AgentCore still documented only, not deployed
