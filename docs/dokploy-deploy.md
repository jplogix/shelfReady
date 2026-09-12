# Deploy ShelfReady on Dokploy

This guide deploys the full stack (Postgres, API, worker, Next.js web) using Dokploy's **Compose** service and `docker-compose.prod.yml`.

## Prerequisites

- Dokploy server with Docker and Traefik
- GitHub repo connected to Dokploy: `jplogix/shelfReady`
- Public domain(s) for web and API (or Dokploy-generated `*.traefik.me` domains)

## 1. Create project

1. In Dokploy, create a project named **ShelfReady**.
2. Use the default **production** environment (or create one).

## 2. Add Compose stack

1. **Add Service → Compose**
2. Connect GitHub:
   - Repository: `jplogix/shelfReady`
   - Branch: `master`
   - Compose file: `docker-compose.prod.yml`
3. Save the compose service.

## 3. Environment variables

Set these on the Compose stack (Dokploy → Compose → Environment). Replace placeholders with your values.

```env
# Database (change password in production)
POSTGRES_USER=shelfready
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=shelfready

# API auth — use the same token for web + API
SHELFREADY_API_TOKEN=<random-token>
NEXT_PUBLIC_API_TOKEN=<same-as-above>

# Public URLs (set after domains are assigned in step 4)
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
CORS_ORIGINS=https://app.yourdomain.com

# Demo mode (no AWS/Bedrock required)
AGENT_MODE=replay
LOOKUP_PROVIDER=replay
```

Optional (live agent mode):

```env
AGENT_MODE=live
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6
```

**Important:** `NEXT_PUBLIC_*` values are baked in at **build** time. After changing them, redeploy/rebuild the `web` service.

## 4. Domains (Traefik)

In Dokploy, add domains to the compose services:

| Service | Port | Example host |
|---------|------|----------------|
| `web`   | 3000 | `app.yourdomain.com` |
| `api`   | 8000 | `api.yourdomain.com` |

Enable HTTPS (Let's Encrypt) on both.

Then update env vars to match:

- `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`
- `CORS_ORIGINS=https://app.yourdomain.com`

Redeploy so the web image rebuilds with the correct API URL.

## 5. Deploy

1. Click **Deploy** on the Compose stack.
2. Wait for Postgres → API (migrations + seed) → worker → web.
3. Verify:
   - `https://api.yourdomain.com/health` → `{"status":"ok","agent_mode":"replay"}`
   - Open `https://app.yourdomain.com` → landing page loads
   - **Try demo catalog** → batch processes and drawer works

## Architecture

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│   web   │────▶│   api   │────▶│ postgres │
│  :3000  │     │  :8000  │     │  :5432   │
└─────────┘     └────┬────┘     └──────────┘
                     │
                ┌────▼────┐
                │ worker  │  (job queue)
                └─────────┘
```

Shared volume `shelfready_storage` holds uploaded/processed assets. Fixtures ship inside the API image.

## Local smoke test (optional)

```bash
cp .env.example .env
# Edit NEXT_PUBLIC_API_URL and CORS_ORIGINS for local ports if needed

docker compose -f docker-compose.prod.yml up --build
```

- Web: http://localhost:3000 (expose ports in compose if testing locally)
- API: http://localhost:8000/health

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Web shows API errors | Check `NEXT_PUBLIC_API_URL` matches public API domain; rebuild web |
| CORS errors | Add web origin to `CORS_ORIGINS`; redeploy API |
| Jobs stuck pending | Confirm `worker` container is running |
| 401 on API calls | Align `SHELFREADY_API_TOKEN` and `NEXT_PUBLIC_API_TOKEN` |

## Vercel frontend only

If you keep the Vercel frontend, point Vercel env `NEXT_PUBLIC_API_URL` at your Dokploy API URL and set `CORS_ORIGINS` on the API to include the Vercel domain.
