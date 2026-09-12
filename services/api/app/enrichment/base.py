"""Product lookup provider types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LookupRecord:
    provider: str
    provider_record_id: str | None
    title: str | None = None
    brand: str | None = None
    model: str | None = None
    mpn: str | None = None
    color: str | None = None
    size: str | None = None
    pack_quantity: str | None = None
    description: str | None = None
    category: str | None = None
    source_url: str | None = None
    images: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LookupResult:
    ok: bool
    query: str
    normalized_query: str
    records: list[LookupRecord] = field(default_factory=list)
    error: str | None = None
    is_replay: bool = False
    is_cached: bool = False
    http_status: int | None = None


class LookupProvider(Protocol):
    name: str

    def lookup_by_barcode(self, normalized_query: str) -> LookupResult: ...

    def search_by_brand_mpn(self, brand: str, mpn: str) -> LookupResult: ...
