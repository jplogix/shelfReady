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

# API auth — server-only. Never NEXT_PUBLIC_API_TOKEN.
ENVIRONMENT=production
SHELFREADY_API_TOKEN=<random-token>
OPERATOR_ACCESS_TOKEN=<same-or-separate-operator-unlock>
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

The web container talks to the API over the compose network (`INTERNAL_API_URL=http://api:8000`) and injects `API_TOKEN` on the server. The browser never receives the write token. Production compose fails if `SHELFREADY_API_TOKEN` or `CORS_ORIGINS` is missing. Do not point `DATABASE_URL` at localhost.

## 4. Domains (Traefik)

In Dokploy, add domains to the compose services:

| Service | Port | Example host |
|---------|------|----------------|
| `web`   | 3000 | `app.yourdomain.com` |
| `api`   | 8000 | `api.yourdomain.com` |

Enable HTTPS (Let's Encrypt) on both.

Then update env vars to match:

- `CORS_ORIGINS=https://app.yourdomain.com`

The API remains separately hosted from the public web origin. Redeploy after changing server env.

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
| 401 on operator writes | Set `OPERATOR_ACCESS_TOKEN` and unlock in the web header, or confirm `API_TOKEN` on the Next.js server |

## Vercel frontend only

If you keep the Vercel frontend, point Vercel env `NEXT_PUBLIC_API_URL` at your Dokploy API URL and set `CORS_ORIGINS` on the API to include the Vercel domain.
