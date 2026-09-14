# Seiko demonstration catalog

This batch is **separate** from the household demo (`demo_catalog.csv`) and the synthetic stress-test (`supplier_catalog.csv`). Customer-facing titles are factual product names. Constructed errors live in `demo_scenario` (operator metadata) and this file.

Prices and stock are **merchant fixture values** for the isolated demo storefront. They are not manufacturer MSRP and are not scraped retail offers.

Official pages verified 2026-09-14:

| Reference | Official US page | Page title | Catalog image code on page |
|-----------|------------------|------------|----------------------------|
| SRPD55 | https://www.seikowatches.com/us-en/products/5sports/srpd55 | SRPD55 \| Seiko Watch Corporation | SRPD55K1 |
| SRPD51 | https://www.seikowatches.com/us-en/products/5sports/srpd51 | SRPD51 \| Seiko Watch Corporation | SRPD51K1 |
| SRPD63 | https://www.seikowatches.com/us-en/products/5sports/srpd63 | SRPD63 \| Seiko Watch Corporation | SRPD63K1 |
| SRPD53 | https://www.seikowatches.com/us-en/products/5sports/srpd53 | SRPD53 \| Seiko Watch Corporation | SRPD53K1 |

`K1` appears in US catalog image filenames on those pages. It is recorded as a regional catalog asset code for the same official product page, not as a different interchangeable model.

Shared manufacturer specifications on those SKX-series pages (do not copy between models without this page evidence): Caliber 4R36; Automatic with manual winding; Approx. 41 hours; stainless steel case; Thickness 13.4mm, Diameter 42.5mm, Lug-to-lug 46.0mm; Hardlex; distance between lugs 22; Water Resistance **10 bar**; Weight 170.0g.

Dial color is **not** listed on those manufacturer pages. Visual review of the official product photograph is recorded separately and is not treated as a manufacturer specification.

## Supplier rows

| SKU | Role | Constructed input | Expected preparation |
|-----|------|-------------------|----------------------|
| SK-SRPD55-01 | Missing-image hero | Brand, model SRPD55, demo price/stock. **No image.** Several specs empty. | Retrieve manufacturer page, store matching photo + specs as evidence, merchant accepts, then publish. |
| SK-SRPD51-01 | Conflicting specification | Supplier case diameter **40mm**. Manufacturer page lists **42.5mm**. Photo is the matching SRPD51 asset. | Detect conflict; preserve supplier 40mm; propose sourced 42.5mm. |
| SK-SRPD63-01 | Mostly complete | Matching SRPD63 photograph; most supported specs present. Brand `SEIKO`. Water resistance `10bar`. | Small normalization only (brand casing; `10bar` → `10 bar`). |
| SK-SRPD53-01 | Wrong-variant image | Model SRPD53 with **SRPD51** photograph (constructed). | Source/model mismatch; resolution required before featured publication. |
| SK-SEIKO5-AMB | Ambiguous reference | Brand Seiko, no model, no image. | Do not guess a watch or borrow a photo. Request missing identity. Stay unpublished. |

Featured public collection publishes only SKUs in `PUBLIC_FEATURED_SKUS` that become eligible after evidence and decisions.

## Images

Downloaded originals: `fixtures/seiko_images/originals/`. The hero photograph may exist in this bundle and in replay fixtures while remaining **unassigned** on the imported SK-SRPD55-01 row. Runtime preparation must still retrieve, persist, and attach it.

Usage: manufacturer-hosted product photography. Official hosting is **not** a license to republish commercially. Isolated demo storefront use is labeled `demo_storefront_only`.
