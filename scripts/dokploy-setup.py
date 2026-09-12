#!/usr/bin/env python3
"""Configure and deploy ShelfReady compose stack on Dokploy."""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
PROJECT_ID = "ZvhyY2TQ-HRo1Yo0t1WmM"
COMPOSE_ID = "5xdstf1KSZCVU-pGOJfon"  # existing stack; set empty to create new
GITHUB_ID = "WtWEWIRZ6KRalbmQ_pgLm"  # jplogix GitHub integration (from existing apps)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
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


def find_environment_id(base_url: str, api_key: str, project_id: str) -> str:
    for candidate in (
        f"environment.all?projectId={project_id}",
        f"environment.byProjectId?projectId={project_id}",
    ):
        try:
            result = api("GET", base_url, api_key, candidate)
        except RuntimeError:
            continue
        if isinstance(result, list) and result:
            env_id = result[0].get("environmentId") or result[0].get("id")
            if env_id:
                return env_id
        if isinstance(result, dict):
            env_id = result.get("environmentId") or result.get("id")
            if env_id:
                return env_id

    # Fallback used by some Dokploy versions: default env id == project id
    return project_id


def main() -> int:
    env = load_env(ENV_FILE)
    base_url = env.get("DOKPLOY_URL", os.environ.get("DOKPLOY_URL", ""))
    api_key = env.get("DOKPLOY_API_KEY", os.environ.get("DOKPLOY_API_KEY", ""))
    if not base_url or not api_key:
        print("Missing DOKPLOY_URL or DOKPLOY_API_KEY in .env", file=sys.stderr)
        return 1

    token = env.get("SHELFREADY_API_TOKEN") or secrets.token_urlsafe(24)
    postgres_password = secrets.token_urlsafe(24)

    environment_id = find_environment_id(base_url, api_key, PROJECT_ID)
    print(f"Using environmentId={environment_id}")

    compose_id = COMPOSE_ID
    if not compose_id:
        compose = api(
            "POST",
            base_url,
            api_key,
            "compose.create",
            {
                "name": "stack",
                "projectId": PROJECT_ID,
                "environmentId": environment_id,
                "composeType": "docker-compose",
            },
        )
        compose_id = compose.get("composeId")
        if not compose_id:
            raise RuntimeError(f"compose.create returned unexpected payload: {compose}")

        print(f"Created compose {compose_id}")

        api(
            "POST",
            base_url,
            api_key,
            "compose.update",
            {
                "composeId": compose_id,
                "sourceType": "github",
                "repository": "shelfReady",
                "owner": "jplogix",
                "branch": "master",
                "composePath": "./docker-compose.prod.yml",
                "githubId": GITHUB_ID,
                "autoDeploy": True,
                "triggerType": "push",
                "enableSubmodules": False,
            },
        )
        print("Linked GitHub repo and compose file")
    else:
        print(f"Using existing compose {compose_id}")

    if not COMPOSE_ID:
        stack_env = "\n".join(
            [
                f"POSTGRES_PASSWORD={postgres_password}",
                f"SHELFREADY_API_TOKEN={token}",
                f"NEXT_PUBLIC_API_TOKEN={token}",
                "AGENT_MODE=replay",
                "LOOKUP_PROVIDER=replay",
                "CORS_ORIGINS=http://localhost:3000",
                "NEXT_PUBLIC_API_URL=http://localhost:8000",
            ]
        )
        api(
            "POST",
            base_url,
            api_key,
            "compose.update",
            {"composeId": compose_id, "env": stack_env},
        )
        print("Saved compose environment variables")
        print(f"SHELFREADY_API_TOKEN={token}")
        print(f"POSTGRES_PASSWORD={postgres_password}")

    deploy = api("POST", base_url, api_key, "compose.deploy", {"composeId": compose_id})
    print("Deploy triggered:", json.dumps(deploy, indent=2) if deploy else "ok")
    print(f"Dokploy project: {base_url}/dashboard/project/{PROJECT_ID}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
