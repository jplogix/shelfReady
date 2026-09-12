"""UPCitemdb live lookup provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.enrichment.base import LookupRecord, LookupResult


class UPCitemdbProvider:
    name = "upcitemdb"
    BASE = "https://api.upcitemdb.com/prod/v1/lookup"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["user_key"] = self.api_key
        return h

    def _request(self, params: dict[str, str]) -> LookupResult:
        query = params.get("upc") or params.get("brand", "")
        normalized = query
        if not self.api_key:
            return LookupResult(
                ok=False,
                query=query,
                normalized_query=normalized,
                error="missing_api_key",
            )

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(self.BASE, params=params, headers=self._headers())
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "2"))
                    time.sleep(min(retry_after, 10))
                    last_error = "rate_limited"
                    continue
                if resp.status_code in {401, 403}:
                    return LookupResult(
                        ok=False,
                        query=query,
                        normalized_query=normalized,
                        error="authentication_error",
                        http_status=resp.status_code,
                    )
                if resp.status_code >= 500:
                    last_error = f"server_error_{resp.status_code}"
                    time.sleep(0.5 * (attempt + 1))
                    continue
                data = resp.json()
                items = data.get("items") or []
                records = [_parse_item(item) for item in items]
                return LookupResult(
                    ok=True,
                    query=query,
                    normalized_query=normalized,
                    records=records,
                    http_status=resp.status_code,
                )
            except httpx.TimeoutException:
                last_error = "timeout"
                time.sleep(0.5 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                break

        return LookupResult(
            ok=False,
            query=query,
            normalized_query=normalized,
            error=last_error or "lookup_failed",
        )

    def lookup_by_barcode(self, normalized_query: str) -> LookupResult:
        return self._request({"upc": normalized_query})

    def search_by_brand_mpn(self, brand: str, mpn: str) -> LookupResult:
        # UPCitemdb search endpoint uses s= query
        query = f"{brand} {mpn}".strip()
        if not self.api_key:
            return LookupResult(ok=False, query=query, normalized_query=query, error="missing_api_key")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    "https://api.upcitemdb.com/prod/v1/search",
                    params={"s": query},
                    headers=self._headers(),
                )
            if resp.status_code != 200:
                return LookupResult(
                    ok=False,
                    query=query,
                    normalized_query=query,
                    error=f"search_http_{resp.status_code}",
                    http_status=resp.status_code,
                )
            items = resp.json().get("items") or []
            records = [_parse_item(item) for item in items[:5]]
            return LookupResult(ok=True, query=query, normalized_query=query, records=records)
        except Exception as exc:  # noqa: BLE001
            return LookupResult(ok=False, query=query, normalized_query=query, error=str(exc))


def _parse_item(item: dict[str, Any]) -> LookupRecord:
    images = []
    if item.get("images"):
        images = list(item["images"]) if isinstance(item["images"], list) else [str(item["images"])]
    return LookupRecord(
        provider="upcitemdb",
        provider_record_id=str(item.get("ean") or item.get("upc") or item.get("title") or ""),
        title=item.get("title"),
        brand=item.get("brand"),
        model=item.get("model"),
        mpn=item.get("mpn"),
        color=item.get("color"),
        size=item.get("size"),
        description=item.get("description"),
        category=item.get("category"),
        source_url=item.get("offers") and None,
        images=images,
        raw={k: v for k, v in item.items() if k not in {"offers"}},
    )
