# Five-minute demo script

**Setup:** `AGENT_MODE=replay`, `LOOKUP_PROVIDER=replay`, API + worker + web running.

1. **Problem** — Supplier watches arrive without photos or with the wrong variant image. ShelfReady retrieves the manufacturer record, stores evidence, and publishes only accepted revisions.
2. **Seiko demonstration** — Operator **Try Seiko demonstration**. SK-SRPD55-01 has no supplier photo. Featured `/store` is this collection (not Seiko-sponsored). Household demo remains available separately.
3. **Prepare** — Worker runs `retrieve_manufacturer_record`. Replay uses official-page HTML fixtures and the downloaded SRPD55 photograph; the UI must label replay.
4. **Workbench** — Side-by-side missing image vs retrieved photo. Accept the image. SRPD51 keeps supplier 40mm on the original row and the 42.5mm manufacturer correction on the proposed listing.
5. **Publish** — Featured ready SKUs only. Ambiguous SK-SEIKO5-AMB and wrong-variant SK-SRPD53-01 stay unpublished.
6. **Store + cart** — Open SRPD55, add to cart, change quantity, remove. Demo cart, no payment.
7. **Evidence** — Preparation page: original → accepted improvements → published result.

**Use only counts visible on screen.**
