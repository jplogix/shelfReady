#!/usr/bin/env python3
"""Add Traefik domains to ShelfReady compose services and update env URLs."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_ID = "5xdstf1KSZCVU-pGOJfon"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def api(method: str, base_url: str, api_key: str, path: str, payload: dict | None = None):
    url = f"{base_url.rstrip('/')}/api/{path}"
    data = None
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{path} failed ({exc.code}): {detail}") from exc


def create_domain(
    base_url: str,
    api_key: str,
    *,
    host: str,
    port: int,
    service_name: str,
) -> dict:
    return api(
        "POST",
        base_url,
        api_key,
        "domain.create",
        {
            "host": host,
            "https": True,
            "certificateType": "letsencrypt",
            "stripPath": False,
            "domainType": "compose",
            "composeId": COMPOSE_ID,
            "serviceName": service_name,
            "port": port,
            "path": "/",
        },
    )


def generate_domain(base_url: str, api_key: str, app_name: str) -> str:
    result = api("POST", base_url, api_key, "domain.generateDomain", {"appName": app_name})
    if isinstance(result, str):
        return result
    return result.get("domain") or result.get("host") or str(result)


def main() -> int:
    env = load_env(ROOT / ".env")
    base_url = env.get("DOKPLOY_URL", os.environ.get("DOKPLOY_URL", ""))
    api_key = env.get("DOKPLOY_API_KEY", os.environ.get("DOKPLOY_API_KEY", ""))

    web = generate_domain(base_url, api_key, "shelfready-web")
    api_domain = generate_domain(base_url, api_key, "shelfready-api")

    print(f"Creating web domain: {web}")
    create_domain(base_url, api_key, host=web, port=3000, service_name="web")
    print(f"Creating api domain: {api_domain}")
    create_domain(base_url, api_key, host=api_domain, port=8000, service_name="api")

    compose = api("GET", base_url, api_key, f"compose.one?composeId={COMPOSE_ID}")
    current_env = compose.get("env") or ""
    lines = [line for line in current_env.splitlines() if line and not line.startswith("NEXT_PUBLIC_API_URL=") and not line.startswith("CORS_ORIGINS=")]
    lines.append(f"NEXT_PUBLIC_API_URL=https://{api_domain}")
    lines.append(f"CORS_ORIGINS=https://{web}")
    api("POST", base_url, api_key, "compose.update", {"composeId": COMPOSE_ID, "env": "\n".join(lines)})
    api("POST", base_url, api_key, "compose.deploy", {"composeId": COMPOSE_ID})
    print(f"Web: https://{web}")
    print(f"API: https://{api_domain}/health")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
