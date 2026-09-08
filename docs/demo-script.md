# Five-minute demo script

**Setup:** `AGENT_MODE=replay`, API + worker + web running. UI shows **Fixture replay mode**.

1. **Problem (30s)** — Small stores spend hours cleaning supplier spreadsheets. ShelfReady is an agent that imports, inspects, escalates, publishes, and verifies — not a chatbot that only recommends.

2. **Load sample (30s)** — Home → **Load sample supplier batch**. Show ~20 products with messy brands, colors, prices, stock, and a prompt-injection description.

3. **Process (45s)** — **Run processing**. Open **Run activity** — real tool actions (`inspect_batch`, etc.), not fake chat. Show counts: corrected / awaiting decisions.

4. **Workbench (45s)** — Open a product: original vs proposed, brand alias, SEO preview with **noindex** note, image classification source `fixture_replay`.

5. **Decisions (60s)** — Decision inbox: resolve **missing price** (edit a value) and one **unknown brand** or **publication** approval. Emphasize approvals bind to product version.

6. **Publish + verify (60s)** — **Publish eligible**. Open Demo store → product page → add in-stock item to cart. Show out-of-stock blocked if present. Mention republish does not duplicate `external_id`.

7. **Close (30s)** — Live mode uses Strands + Bedrock with the same tools; replay never pretends to be live. AgentCore is documented, not required for the demo.

**Use only counts visible on screen — do not invent accuracy % or time saved.**
