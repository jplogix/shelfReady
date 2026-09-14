# Seiko demonstration — recording script

Setup: `AGENT_MODE=replay`, `LOOKUP_PROVIDER=replay`. API + worker + web. Isolated batch via `python scripts/reset_seiko_demo.py --apply` or workspace **Try Seiko demonstration**.

1. Open `/store`. Featured collection is Seiko 5 Sports demonstration listings (not Seiko-sponsored). Household fixtures remain in the repo and operator workspace.
2. Operator workspace → open SK-SRPD55-01 **before** processing if you imported without running the worker: supplier row has brand/model/price/stock and **no photo**.
3. **Prepare products**. Activity includes `retrieve_manufacturer_record` (replay of the official SRPD55 page HTML + stored photograph — labeled replay, not a live crawl when lookup is replay).
4. Workbench: original “no photo”; proposed listing with the retrieved SRPD55 photograph and supported specs. Image decision shows preview, model, source page, retrieval time, match rationale, usage/suitability. **Use this image**.
5. SK-SRPD51-01: supplier case diameter 40mm vs manufacturer 42.5mm — accept the sourced correction; original 40mm remains on the supplier record.
6. Publish featured ready SKUs. Open the SRPD55 storefront route: title, merchant demo price, image loads, specification table, preparation link.
7. Add to cart → quantity → remove. Banner: demo cart, no payment.
8. Preparation page outcome: added a product photo and completed supported specifications (counts from accepted diffs/evidence).

Do not claim live Bedrock or live seikowatches.com fetch unless those modes were actually used. Do not claim commercial image license.
