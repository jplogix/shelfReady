"""Fixture-backed lookup provider for replay mode."""

from __future__ import annotations

import json
from pathlib import Path

from app.enrichment.base import LookupRecord, LookupResult
from app.enrichment.upcitemdb import _parse_item


class ReplayLookupProvider:
    name = "replay"

    def __init__(self, fixtures_root: Path) -> None:
        self.fixtures_root = fixtures_root
        self.upc_dir = fixtures_root / "replay" / "upc"

    def _load(self, key: str) -> dict | None:
        path = self.upc_dir / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def lookup_by_barcode(self, normalized_query: str) -> LookupResult:
        data = self._load(normalized_query)
        if data is None:
            return LookupResult(
                ok=True,
                query=normalized_query,
                normalized_query=normalized_query,
                records=[],
                is_replay=True,
            )
        items = data.get("items") or []
        records = [_parse_item(item) for item in items]
        return LookupResult(
            ok=True,
            query=normalized_query,
            normalized_query=normalized_query,
            records=records,
            is_replay=True,
        )

    def search_by_brand_mpn(self, brand: str, mpn: str) -> LookupResult:
        key = f"search_{brand}_{mpn}".lower().replace(" ", "_").replace("/", "_")
        data = self._load(key)
        query = f"{brand} {mpn}".strip()
        if data is None:
            return LookupResult(
                ok=True,
                query=query,
                normalized_query=query,
                records=[],
                is_replay=True,
            )
        items = data.get("items") or []
        records = [_parse_item(item) for item in items]
        return LookupResult(
            ok=True,
            query=query,
            normalized_query=query,
            records=records,
            is_replay=True,
        )
