# Devpost submission copy

## Project description

ShelfReady is an evidence-backed product-onboarding agent for small e-commerce teams. Supplier catalogs often arrive with missing photographs, inconsistent names, incorrect variants, and incomplete attributes. Correcting those records manually is slow, while blindly automating changes can publish inaccurate listings.

ShelfReady imports a supplier CSV, preserves the original record, and prepares a proposed storefront revision with field-level provenance. Safe normalization is handled deterministically. Ambiguous or consequential changes become explicit merchant decisions rather than silent guesses. Accepted products are published idempotently to an isolated demo storefront and verified through the same retrieval, structured-data, inventory, and cart paths a shopper uses.

The featured demonstration follows five Seiko 5 Sports supplier rows. One arrives without a product image, one contains an ambiguous reference, and another contains a wrong-variant image. ShelfReady retrieves matching manufacturer evidence, keeps unsuitable or unresolved products unpublished, and gives the operator an original-to-published transformation view.

The backend uses FastAPI, PostgreSQL, a persisted worker, and the Strands Agents SDK with Amazon Bedrock in live mode. Structured model output is validated against evidence IDs, field allowlists, types, and the current product revision before application code can use it. Replay mode demonstrates the same validation, decision, publication, and verification services without model calls and is visibly labeled in the interface.

## Who it is for

Small merchants, catalog operators, and e-commerce teams that need automation but cannot sacrifice control, traceability, or product accuracy.

## Why it matters

ShelfReady reduces repetitive catalog work while keeping humans responsible for uncertain decisions. Every published change can be traced back to supplier data, external evidence, deterministic normalization, or an explicit merchant decision.

## Links

- Source: https://github.com/jplogix/shelfReady
- Live demonstration: https://shelfready.svgfy.com
- Architecture: https://github.com/jplogix/shelfReady/blob/master/docs/architecture.md
- Demo video: ADD_PUBLIC_YOUTUBE_OR_VIMEO_URL

## Testing instructions

The public storefront, product pages, cart, and preparation evidence are available without credentials at https://shelfready.svgfy.com. Start with the featured collection, open a product, inspect **How this was prepared**, and exercise cart quantity and removal behavior.

To run the complete operator workflow, follow the repository README. Use `AGENT_MODE=replay` and `LOOKUP_PROVIDER=replay` for a credential-free deterministic demonstration. Replay is labeled in the UI and uses the same persisted decision, publication, and verification services as live mode. Live agent execution additionally requires AWS credentials with Amazon Bedrock access.

## Video checklist — maximum five minutes

1. State the catalog-quality problem, intended user, and why human review matters.
2. Show **Try Seiko demonstration** and identify the missing-image product.
3. Run **Prepare products** and point out the replay-mode label.
4. Show the original record, evidence-backed proposal, and merchant decision.
5. Publish eligible products while ambiguous/wrong-variant cases remain blocked.
6. Open the public storefront, product provenance, and cart.
7. End with the architecture diagram and the live/source links.

Before submitting, replace the video placeholder above and add the entrant's AWS Builder ID in the Devpost form.
