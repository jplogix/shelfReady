#!/usr/bin/env python3
"""Check Dokploy compose deployment status."""

from __future__ import annotations

import json
import os
import sys
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


def main() -> int:
    env = load_env(ROOT / ".env")
    base_url = env.get("DOKPLOY_URL", os.environ.get("DOKPLOY_URL", ""))
    api_key = env.get("DOKPLOY_API_KEY", os.environ.get("DOKPLOY_API_KEY", ""))
    url = f"{base_url.rstrip('/')}/api/compose.one?composeId={COMPOSE_ID}"
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print(json.dumps(
        {
            "composeId": data.get("composeId"),
            "name": data.get("name"),
            "composeStatus": data.get("composeStatus"),
            "sourceType": data.get("sourceType"),
            "repository": data.get("repository"),
            "branch": data.get("branch"),
            "composePath": data.get("composePath"),
            "domains": data.get("domains", []),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
