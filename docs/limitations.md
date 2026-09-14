# Known limitations

- Single operator workspace; no multi-tenant billing.
- One concurrent processing job (MVP simplification).
- Demo store only — not Shopify/Medusa; no payments.
- Images: uploaded files and bundled fixtures only (no remote URL fetch).
- Live image classification requires a live model path; replay uses labeled fixture classes.
- SEO output is an inspectable preview; demo is **noindex**.
- AgentCore Runtime is documented, not deployed in this package.
- Live Bedrock structured output is only verified when AWS credentials are present; CI uses a controlled fake agent.
- Verification exercises the store adapter (slug retrieval, JSON-LD, cart add/block), not a headless pass over Next.js HTML.
- Production must host API and worker separately from the browser; localhost database/API defaults are rejected when `ENVIRONMENT=production`.
- Nested `apps/web` may contain a local git metadata folder from scaffolding; use the repository root as the project git root when publishing.
- Next.js 15.3.1 was scaffolded as a stable App Router baseline; review upstream security advisories before production use.
