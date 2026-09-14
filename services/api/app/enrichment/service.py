"""Enrichment orchestration: cache, budget, evidence persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    EvidenceAcceptance,
    FieldEvidence,
    LookupCache,
    MatchOutcome,
    Product,
    ProductStatus,
    ProductVersion,
)
from app.enrichment.base import LookupProvider, LookupRecord, LookupResult
from app.enrichment.compare import FieldComparison, compare_record, overall_outcome
from app.enrichment.replay import ReplayLookupProvider
from app.enrichment.upcitemdb import UPCitemdbProvider
from app.policy.identifiers import normalize_lookup_query, pick_lookup_identifier, validate_gtin
from app.policy.validate import compute_diffs, validate_product_fields


class EnrichmentBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self._seen: set[tuple[str, str]] = set()

    def allow(self, provider: str, query: str) -> bool:
        key = (provider, query)
        if key in self._seen:
            return True
        if self.used >= self.limit:
            return False
        self._seen.add(key)
        self.used += 1
        return True


def get_provider(fixtures_root) -> LookupProvider:
    settings = get_settings()
    if settings.lookup_provider == "upcitemdb":
        return UPCitemdbProvider(
            settings.upcitemdb_api_key,
            timeout=settings.lookup_timeout_seconds,
            max_retries=settings.lookup_max_retries,
        )
    return ReplayLookupProvider(fixtures_root)


def _cache_get(db: Session, provider: str, query: str) -> dict | None:
    row = db.scalar(
        select(LookupCache).where(
            LookupCache.provider == provider,
            LookupCache.normalized_query == query,
            LookupCache.expires_at > datetime.now(timezone.utc),
        )
    )
    return row.response if row else None


def _cache_set(db: Session, provider: str, query: str, response: dict, *, ttl_hours: int = 24) -> None:
    existing = db.scalar(
        select(LookupCache).where(
            LookupCache.provider == provider,
            LookupCache.normalized_query == query,
        )
    )
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    if existing:
        existing.response = response
        existing.expires_at = expires
    else:
        db.add(
            LookupCache(
                id=uuid.uuid4(),
                provider=provider,
                normalized_query=query,
                response=response,
                expires_at=expires,
            )
        )


def _lookup_with_cache(
    db: Session,
    provider: LookupProvider,
    budget: EnrichmentBudget,
    *,
    barcode: str | None = None,
    brand: str | None = None,
    mpn: str | None = None,
) -> LookupResult:
    if barcode:
        query = normalize_lookup_query(barcode)
        cached = _cache_get(db, provider.name, query)
        if cached is not None:
            items = cached.get("items") or []
            from app.enrichment.upcitemdb import _parse_item

            return LookupResult(
                ok=True,
                query=barcode,
                normalized_query=query,
                records=[_parse_item(i) for i in items],
                is_cached=True,
                is_replay=getattr(provider, "name", "") == "replay",
            )
        if not budget.allow(provider.name, query):
            return LookupResult(
                ok=False,
                query=barcode,
                normalized_query=query,
                error="budget_exceeded",
            )
        result = provider.lookup_by_barcode(query)
        if result.ok:
            _cache_set(db, provider.name, query, {"items": [r.raw for r in result.records]})
        return result

    if brand and mpn:
        query = f"{brand} {mpn}".strip()
        norm = query.lower()
        if not budget.allow(provider.name, norm):
            return LookupResult(ok=False, query=query, normalized_query=norm, error="budget_exceeded")
        return provider.search_by_brand_mpn(brand, mpn)

    return LookupResult(ok=False, query="", normalized_query="", error="no_query")


def _persist_evidence(
    db: Session,
    product: Product,
    version: ProductVersion,
    comparison: FieldComparison,
    record: LookupRecord,
    lookup_result: LookupResult,
    *,
    provider_name: str,
) -> FieldEvidence:
    ev = FieldEvidence(
        id=uuid.uuid4(),
        product_id=product.id,
        product_version_id=version.id,
        field_name=comparison.field_name,
        original_supplier_value=comparison.supplier_value,
        proposed_value=comparison.evidence_value if comparison.outcome == MatchOutcome.matching_evidence else None,
        source_provider=provider_name,
        source_url=record.source_url,
        provider_record_id=record.provider_record_id,
        lookup_identifier=lookup_result.normalized_query,
        lookup_query=lookup_result.query,
        match_outcome=comparison.outcome,
        match_explanation=comparison.explanation,
        acceptance_status=EvidenceAcceptance.pending,
        is_cached=lookup_result.is_cached,
        is_replay=lookup_result.is_replay,
        raw_response=record.raw,
    )
    db.add(ev)
    return ev


def enrich_product(
    db: Session,
    product: Product,
    version: ProductVersion,
    original: dict[str, Any],
    provider: LookupProvider,
    budget: EnrichmentBudget,
) -> list[FieldEvidence]:
    """Run identifier lookup and persist field evidence + decisions."""
    evidence_rows: list[FieldEvidence] = []
    field_name, raw_id = pick_lookup_identifier(original)
    proposed = dict(version.proposed)

    if raw_id:
        validation = validate_gtin(raw_id)
        if not validation.valid:
            ev = FieldEvidence(
                id=uuid.uuid4(),
                product_id=product.id,
                product_version_id=version.id,
                field_name=field_name or "gtin",
                original_supplier_value=validation.raw,
                proposed_value=None,
                source_provider=provider.name,
                lookup_identifier=validation.raw,
                lookup_query=validation.raw,
                match_outcome=MatchOutcome.invalid_identifier,
                match_explanation=f"Identifier failed validation: {validation.reason}.",
                acceptance_status=EvidenceAcceptance.rejected,
                is_replay=provider.name == "replay",
            )
            db.add(ev)
            evidence_rows.append(ev)
            proposed["identifier_valid"] = False
            proposed["identifier_raw"] = validation.raw
            version.proposed = proposed
            return evidence_rows

        lookup = _lookup_with_cache(db, provider, budget, barcode=validation.normalized or raw_id)
        if not lookup.ok:
            outcome = MatchOutcome.lookup_unavailable
            if lookup.error == "budget_exceeded":
                outcome = MatchOutcome.lookup_unavailable
            ev = FieldEvidence(
                id=uuid.uuid4(),
                product_id=product.id,
                product_version_id=version.id,
                field_name=field_name or "gtin",
                original_supplier_value=validation.raw,
                proposed_value=None,
                source_provider=provider.name,
                lookup_identifier=validation.raw,
                lookup_query=lookup.query,
                match_outcome=outcome,
                match_explanation=f"Lookup unavailable: {lookup.error or 'unknown'}.",
                acceptance_status=EvidenceAcceptance.pending,
                is_cached=lookup.is_cached,
                is_replay=lookup.is_replay,
            )
            db.add(ev)
            evidence_rows.append(ev)
            proposed["identifier_raw"] = validation.raw
            proposed["identifier_normalized"] = validation.normalized
            version.proposed = proposed
            return evidence_rows

        if not lookup.records:
            ev = FieldEvidence(
                id=uuid.uuid4(),
                product_id=product.id,
                product_version_id=version.id,
                field_name=field_name or "gtin",
                original_supplier_value=validation.raw,
                proposed_value=None,
                source_provider=provider.name,
                lookup_identifier=validation.raw,
                lookup_query=lookup.query,
                match_outcome=MatchOutcome.no_match,
                match_explanation="No matching product found for this identifier.",
                is_cached=lookup.is_cached,
                is_replay=lookup.is_replay,
            )
            db.add(ev)
            evidence_rows.append(ev)
            proposed["identifier_raw"] = validation.raw
            proposed["identifier_normalized"] = validation.normalized
            version.proposed = proposed
            return evidence_rows

        record = lookup.records[0]
        comparisons = compare_record(original, record)
        outcome = overall_outcome(comparisons)

        for comp in comparisons:
            evidence_rows.append(
                _persist_evidence(
                    db,
                    product,
                    version,
                    comp,
                    record,
                    lookup,
                    provider_name=provider.name,
                )
            )

        # Apply safe enrichments for missing fields only
        enrich_map = {
            "brand": record.brand,
            "model": record.model or record.mpn,
            "size": record.size,
            "title": record.title,
        }
        for fld, val in enrich_map.items():
            if val and not original.get(fld):
                proposed[fld] = val
                provenance = dict(version.provenance)
                provenance[fld] = "external_reference"
                version.provenance = provenance

        proposed["identifier_raw"] = validation.raw
        proposed["identifier_normalized"] = validation.normalized
        version.proposed = proposed

        if outcome == MatchOutcome.conflicting_evidence:
            conflicts = [c for c in comparisons if c.outcome == MatchOutcome.conflicting_evidence]
            db.add(
                Decision(
                    id=uuid.uuid4(),
                    workspace_id=product.workspace_id,
                    batch_id=product.batch_id,
                    product_id=product.id,
                    product_version_id=version.id,
                    kind=DecisionKind.conflicting_variant,
                    status=DecisionStatus.pending,
                    field_name=conflicts[0].field_name if conflicts else "variant",
                    original_value=conflicts[0].supplier_value if conflicts else original,
                    proposed_value=conflicts[0].evidence_value if conflicts else None,
                    evidence={"conflicts": [{"field": c.field_name, "supplier": c.supplier_value, "record": c.evidence_value} for c in conflicts]},
                    reason="Barcode record conflicts with supplier variant information.",
                    consequence="Choose the correct variant or keep unresolved.",
                    risk_tier="approval",
                )
            )
        elif outcome == MatchOutcome.matching_evidence:
            for comp in comparisons:
                if comp.outcome == MatchOutcome.matching_evidence and comp.supplier_value in (None, ""):
                    db.add(
                        Decision(
                            id=uuid.uuid4(),
                            workspace_id=product.workspace_id,
                            batch_id=product.batch_id,
                            product_id=product.id,
                            product_version_id=version.id,
                            kind=DecisionKind.accept_enrichment,
                            status=DecisionStatus.pending,
                            field_name=comp.field_name,
                            original_value=comp.supplier_value,
                            proposed_value=comp.evidence_value,
                            evidence={"source": provider.name, "lookup": lookup.query},
                            reason=comp.explanation,
                            consequence="Accept to apply this supported correction from external evidence.",
                            risk_tier="review",
                        )
                    )
        elif outcome == MatchOutcome.possible_match:
            db.add(
                Decision(
                    id=uuid.uuid4(),
                    workspace_id=product.workspace_id,
                    batch_id=product.batch_id,
                    product_id=product.id,
                    product_version_id=version.id,
                    kind=DecisionKind.confirm_product_match,
                    status=DecisionStatus.pending,
                    field_name="identity",
                    original_value={"title": original.get("title"), "brand": original.get("brand")},
                    proposed_value={"title": record.title, "brand": record.brand},
                    evidence={"source": provider.name},
                    reason="External record may match this product but requires confirmation.",
                    consequence="Confirm product match before applying external data.",
                    risk_tier="approval",
                )
                )

        _reconcile_after_enrichment(db, product, version)
        return evidence_rows

    # No barcode: brand+mpn search if specific enough
    brand = original.get("brand")
    mpn = original.get("mpn") or original.get("model")
    if brand and mpn and len(str(mpn).strip()) >= 3:
        lookup = _lookup_with_cache(db, provider, budget, brand=str(brand), mpn=str(mpn))
        if lookup.ok and lookup.records:
            record = lookup.records[0]
            db.add(
                Decision(
                    id=uuid.uuid4(),
                    workspace_id=product.workspace_id,
                    batch_id=product.batch_id,
                    product_id=product.id,
                    product_version_id=version.id,
                    kind=DecisionKind.confirm_product_match,
                    status=DecisionStatus.pending,
                    field_name="identity",
                    original_value={"brand": brand, "mpn": mpn},
                    proposed_value={"title": record.title, "brand": record.brand, "mpn": record.mpn},
                    evidence={"source": provider.name, "candidates": len(lookup.records)},
                    reason="Brand+MPN search returned candidate matches requiring confirmation.",
                    consequence="Confirm before using external identifier or attributes.",
                    risk_tier="approval",
                )
            )

    _reconcile_after_enrichment(db, product, version)
    db.flush()
    return evidence_rows


def _reconcile_after_enrichment(db: Session, product: Product, version: ProductVersion) -> None:
    """Drop stale missing-field blockers once evidence filled the proposed row."""
    has_primary = any(img.is_primary for img in product.images)
    result = validate_product_fields(dict(version.proposed), has_primary_image=has_primary)
    version.proposed = result["proposed"]
    version.diffs = compute_diffs(version.original or {}, version.proposed)
    version.blockers = result["blockers"] + [{"kind": "review", **r} for r in result["reviews"]]
    version.is_publishable = result["is_publishable"]
    filled = {key for key in ("title", "brand", "model", "size") if version.proposed.get(key)}
    pending = db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.status == DecisionStatus.pending,
        )
    ).all()
    for decision in pending:
        if decision.kind == DecisionKind.other and decision.field_name in filled:
            decision.status = DecisionStatus.approved
            decision.proposed_value = version.proposed.get(decision.field_name)
    remaining = [
        d
        for d in pending
        if d.status == DecisionStatus.pending and not (d.kind == DecisionKind.other and d.field_name in filled)
    ]
    if version.is_publishable and not remaining:
        product.status = ProductStatus.ready
    db.flush()
