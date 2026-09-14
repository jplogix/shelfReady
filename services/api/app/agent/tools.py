"""Strands agent tools with real persistence and effects."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentAction,
    Batch,
    Decision,
    DecisionKind,
    DecisionStatus,
    FieldEvidence,
    Job,
    JobStatus,
    NormalizationRule,
    Product,
    ProductReadiness,
    ProductStatus,
    ProductVersion,
    RuleScope,
    RunSummary,
)
from app.enrichment.service import EnrichmentBudget, enrich_product, get_provider
from app.policy.readiness import refresh_product_readiness
from app.services.catalog import process_product, median_prices
from app.store.demo import DemoStoreAdapter


class ToolContext:
    def __init__(self, db: Session, job: Job, batch: Batch) -> None:
        self.db = db
        self.job = job
        self.batch = batch
        self.store = DemoStoreAdapter()

    def log(self, tool_name: str, inp: dict, out: dict, *, success: bool = True, evidence: str | None = None) -> None:
        self.db.add(
            AgentAction(
                id=uuid.uuid4(),
                job_id=self.job.id,
                tool_name=tool_name,
                input_payload=inp,
                output_payload=out,
                success=success,
                evidence_summary=evidence,
            )
        )
        self.db.flush()


_CTX: ToolContext | None = None


def set_tool_context(ctx: ToolContext | None) -> None:
    global _CTX
    _CTX = ctx


def get_ctx() -> ToolContext:
    if _CTX is None:
        raise RuntimeError("Tool context not set")
    return _CTX


def inspect_batch(batch_id: str) -> dict[str, Any]:
    """Inspect imported batch products and status counts."""
    ctx = get_ctx()
    products = ctx.db.scalars(select(Product).where(Product.batch_id == ctx.batch.id)).all()
    counts: dict[str, int] = {}
    for p in products:
        counts[p.status.value] = counts.get(p.status.value, 0) + 1
    out = {
        "batch_id": batch_id,
        "product_count": len(products),
        "counts": counts,
        "product_ids": [str(p.id) for p in products],
        "skus": [p.sku for p in products],
    }
    ctx.log("inspect_batch", {"batch_id": batch_id}, out, evidence=f"{len(products)} products")
    return out


def get_product_evidence(product_id: str) -> dict[str, Any]:
    """Retrieve original/proposed fields, images, and open decisions for a product."""
    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product:
        out = {"error": "not_found"}
        ctx.log("get_product_evidence", {"product_id": product_id}, out, success=False)
        return out
    version = None
    if product.current_version_id:
        version = ctx.db.get(ProductVersion, product.current_version_id)
    decisions = ctx.db.scalars(
        select(Decision).where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
    ).all()
    out = {
        "product_id": str(product.id),
        "sku": product.sku,
        "status": product.status.value,
        "original": version.original if version else None,
        "proposed": version.proposed if version else None,
        "seo": version.seo if version else None,
        "blockers": version.blockers if version else [],
        "images": [
            {
                "id": str(i.id),
                "class": i.image_class.value,
                "is_primary": i.is_primary,
                "path": i.derivative_path or i.original_path,
                "classification_source": i.classification_source,
                "source_kind": i.source_kind,
                "usage_permission": i.usage_permission,
                "suitability": i.suitability,
            }
            for i in product.images
        ],
        "pending_decisions": [
            {"id": str(d.id), "kind": d.kind.value, "reason": d.reason, "field_name": d.field_name}
            for d in decisions
        ],
        "field_evidence": [
            {
                "id": str(e.id),
                "field_name": e.field_name,
                "match_outcome": e.match_outcome.value,
                "match_explanation": e.match_explanation,
                "proposed_value": e.proposed_value,
                "source_provider": e.source_provider,
                "is_replay": e.is_replay,
                "is_cached": e.is_cached,
            }
            for e in ctx.db.scalars(
                select(FieldEvidence).where(FieldEvidence.product_id == product.id)
            ).all()
        ],
    }
    ctx.log("get_product_evidence", {"product_id": product_id}, out, evidence=product.sku)
    return out


def get_normalization_rules() -> dict[str, Any]:
    """Return active and inactive normalization rules for the workspace."""
    ctx = get_ctx()
    rules = ctx.db.scalars(
        select(NormalizationRule).where(NormalizationRule.workspace_id == ctx.batch.workspace_id)
    ).all()
    out = {
        "rules": [
            {
                "id": str(r.id),
                "type": r.rule_type,
                "source": r.source_value,
                "target": r.target_value,
                "active": r.active,
            }
            for r in rules
        ]
    }
    ctx.log("get_normalization_rules", {}, out, evidence=f"{len(rules)} rules")
    return out


def inspect_product_images(product_id: str) -> dict[str, Any]:
    """Inspect image classification and primary selection for a product."""
    return get_product_evidence(product_id)  # shares evidence path; logged distinctly below


def propose_product_patch(product_id: str, patch_json: str) -> dict[str, Any]:
    """Apply an allowlisted proposed field patch. Price/stock/identifiers are rejected."""
    import json

    from app.agent.evidence import ALLOWLISTED_FIELDS, FORBIDDEN_AUTOFILL_FIELDS, EvidenceValidationError
    from app.agent.schemas import ProductPatchProposal
    from app.agent.apply import apply_patch_proposal

    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product or not product.current_version_id:
        out = {"error": "not_found"}
        ctx.log("propose_product_patch", {"product_id": product_id}, out, success=False)
        return out
    current = ctx.db.get(ProductVersion, product.current_version_id)
    assert current
    patch = json.loads(patch_json) if isinstance(patch_json, str) else patch_json
    if not isinstance(patch, dict):
        out = {"error": "invalid_patch"}
        ctx.log("propose_product_patch", {"product_id": product_id}, out, success=False)
        return out
    evidence_ids = patch.pop("evidence_references", None) or patch.pop("evidence_ids", None) or []
    if isinstance(evidence_ids, str):
        evidence_ids = [evidence_ids]
    forbidden = set(patch) & FORBIDDEN_AUTOFILL_FIELDS
    if forbidden:
        out = {"error": "forbidden_fields", "fields": sorted(forbidden)}
        ctx.log("propose_product_patch", {"product_id": product_id, "patch": patch}, out, success=False)
        return out
    unknown = set(patch) - ALLOWLISTED_FIELDS
    if unknown:
        out = {"error": "field_not_allowed", "fields": sorted(unknown)}
        ctx.log("propose_product_patch", {"product_id": product_id, "patch": patch}, out, success=False)
        return out
    applied: list[dict[str, Any]] = []
    current_version = current
    try:
        for field, value in patch.items():
            proposal = ProductPatchProposal(
                field=field,  # type: ignore[arg-type]
                proposed_value=value,
                unresolved=value is None,
                evidence_references=[str(x) for x in evidence_ids],
                explanation="Agent-proposed allowlisted correction",
            )
            applied.append(
                apply_patch_proposal(
                    ctx.db,
                    product,
                    current_version,
                    proposal,
                    expected_version_id=current_version.id,
                )
            )
            product = ctx.db.get(Product, product.id)
            assert product and product.current_version_id
            current_version = ctx.db.get(ProductVersion, product.current_version_id)
            assert current_version
    except (EvidenceValidationError, ValueError) as exc:
        out = {"error": "evidence_validation_failed", "detail": str(exc)}
        ctx.log("propose_product_patch", {"product_id": product_id, "patch": patch}, out, success=False)
        return out
    out = {"product_id": product_id, "version_id": str(current_version.id), "applied": applied}
    ctx.log("propose_product_patch", {"product_id": product_id, "patch": patch}, out)
    return out


def validate_product(product_id: str) -> dict[str, Any]:
    """Re-validate current proposed fields and update publishability."""
    from app.policy.validate import validate_product_fields

    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product or not product.current_version_id:
        return {"error": "not_found"}
    version = ctx.db.get(ProductVersion, product.current_version_id)
    assert version
    has_primary = any(i.is_primary for i in product.images)
    result = validate_product_fields(
        dict(version.proposed),
        has_primary_image=has_primary,
    )
    version.proposed = result["proposed"]
    version.blockers = result["blockers"] + [{"kind": "review", **r} for r in result["reviews"]]
    version.is_publishable = result["is_publishable"]
    pending = ctx.db.scalars(
        select(Decision).where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
    ).all()
    if pending or not result["is_publishable"]:
        product.status = ProductStatus.needs_review
        version.is_publishable = False
    else:
        product.status = ProductStatus.ready
    out = {
        "product_id": product_id,
        "is_publishable": version.is_publishable,
        "blockers": version.blockers,
        "status": product.status.value,
    }
    ctx.log("validate_product", {"product_id": product_id}, out)
    return out


def create_decision_request(
    product_id: str,
    kind: str,
    reason: str,
    consequence: str,
    field_name: str = "",
    original_value: str = "",
    proposed_value: str = "",
) -> dict[str, Any]:
    """Create a persistent human decision request for ambiguous or consequential changes."""
    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product:
        return {"error": "not_found"}
    try:
        kind_enum = DecisionKind(kind)
    except ValueError:
        kind_enum = DecisionKind.other
    d = Decision(
        id=uuid.uuid4(),
        workspace_id=product.workspace_id,
        batch_id=product.batch_id,
        product_id=product.id,
        product_version_id=product.current_version_id,
        kind=kind_enum,
        status=DecisionStatus.pending,
        field_name=field_name or None,
        original_value=original_value,
        proposed_value=proposed_value,
        evidence={},
        reason=reason,
        consequence=consequence,
        risk_tier="review",
    )
    ctx.db.add(d)
    product.status = ProductStatus.needs_review
    ctx.db.flush()
    out = {"decision_id": str(d.id), "kind": kind_enum.value}
    ctx.log("create_decision_request", {"product_id": product_id, "kind": kind}, out)
    return out


def lookup_product_identifier(product_id: str) -> dict[str, Any]:
    """Look up product identifiers and persist field-level evidence."""
    from pathlib import Path

    from app.config import get_settings
    from app.policy.identifiers import pick_lookup_identifier

    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product or not product.current_version_id:
        out = {"error": "not_found"}
        ctx.log("lookup_product_identifier", {"product_id": product_id}, out, success=False)
        return out
    version = ctx.db.get(ProductVersion, product.current_version_id)
    assert version
    _field_name, raw_id = pick_lookup_identifier(version.original or {})
    brand = (version.original or {}).get("brand")
    mpn = (version.original or {}).get("mpn") or (version.original or {}).get("model")
    if not raw_id and not (brand and mpn and len(str(mpn).strip()) >= 3):
        out = {
            "product_id": product_id,
            "skipped": True,
            "reason": "no_useful_identifier",
            "evidence_count": 0,
        }
        ctx.log("lookup_product_identifier", {"product_id": product_id}, out, evidence="skipped: no identifier")
        return out
    settings = get_settings()
    fixtures = settings.fixtures_root
    if not fixtures.is_absolute():
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        fixtures = alt if alt.exists() else Path.cwd() / fixtures
    provider = get_provider(fixtures)
    budget = EnrichmentBudget(settings.lookup_budget_per_run)
    rows = enrich_product(ctx.db, product, version, version.original, provider, budget)
    refresh_product_readiness(ctx.db, product)
    out = {
        "product_id": product_id,
        "evidence_count": len(rows),
        "readiness": product.readiness.value if product.readiness else None,
    }
    ctx.log("lookup_product_identifier", {"product_id": product_id}, out, evidence=f"{len(rows)} evidence rows")
    return out


def retrieve_manufacturer_record(product_id: str) -> dict[str, Any]:
    """Retrieve the matching manufacturer page, specs, and photograph for an exact model."""
    from app.services.manufacturer_recovery import retrieve_manufacturer_record as recover

    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product:
        out = {"error": "not_found"}
        ctx.log("retrieve_manufacturer_record", {"product_id": product_id}, out, success=False)
        return out
    out = recover(ctx.db, product)
    ctx.log(
        "retrieve_manufacturer_record",
        {"product_id": product_id},
        {k: v for k, v in out.items() if k != "specifications"},
        success=bool(out.get("ok")),
        evidence=out.get("manufacturer_reference") or out.get("error"),
    )
    return out


def publish_product(product_id: str) -> dict[str, Any]:
    """Publish an eligible product to the internal demo store. Enforces approvals in code."""
    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product or not product.current_version_id:
        out = {"error": "not_found"}
        ctx.log("publish_product", {"product_id": product_id}, out, success=False)
        return out
    version = ctx.db.get(ProductVersion, product.current_version_id)
    assert version
    workspace = product.workspace

    if not product.approved_version_id or str(product.approved_version_id) != str(version.id):
        out = {
            "error": "approval_required",
            "detail": "Publication blocked: product revision not approved for publish.",
        }
        ctx.log("publish_product", {"product_id": product_id}, out, success=False)
        return out

    pending = ctx.db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.status == DecisionStatus.pending,
        )
    ).all()
    if pending:
        out = {"error": "pending_decisions", "count": len(pending)}
        ctx.log("publish_product", {"product_id": product_id}, out, success=False)
        return out

    # Re-validate publishability
    from app.policy.validate import validate_product_fields

    has_primary = any(i.is_primary for i in product.images)
    result = validate_product_fields(dict(version.proposed), has_primary_image=has_primary)
    if not result["is_publishable"] and not (
        # allow zero stock if otherwise valid — validate_product_fields treats missing image as block
        result["proposed"].get("price") and result["proposed"].get("sku")
    ):
        # Missing price always blocks
        if any(b["kind"] == "missing_price" for b in result["blockers"]):
            out = {"error": "not_publishable", "blockers": result["blockers"]}
            ctx.log("publish_product", {"product_id": product_id}, out, success=False)
            return out
    if any(b["kind"] == "missing_price" for b in result["blockers"]):
        out = {"error": "missing_price", "blockers": result["blockers"]}
        ctx.log("publish_product", {"product_id": product_id}, out, success=False)
        return out

    product.status = ProductStatus.publishing
    sp = ctx.store.publish_product(ctx.db, product, version)
    product.store_product_id = sp.id
    product.store_slug = sp.slug
    product.status = ProductStatus.published
    refresh_product_readiness(ctx.db, product)
    ctx.db.flush()
    out = {
        "product_id": product_id,
        "store_product_id": str(sp.id),
        "external_id": sp.external_id,
        "slug": sp.slug,
        "idempotent": True,
    }
    ctx.log("publish_product", {"product_id": product_id}, out, evidence=sp.external_id)
    return out


def verify_published_product(product_id: str) -> dict[str, Any]:
    """Verify a published product is retrievable, consistent, and cart-correct."""
    ctx = get_ctx()
    product = ctx.db.get(Product, uuid.UUID(product_id))
    if not product or not product.store_product_id:
        out = {"error": "not_published"}
        ctx.log("verify_published_product", {"product_id": product_id}, out, success=False)
        return out
    from app.db.models import StoreProduct

    sp = ctx.db.get(StoreProduct, product.store_product_id)
    if not sp:
        out = {"error": "store_row_missing"}
        ctx.log("verify_published_product", {"product_id": product_id}, out, success=False)
        return out
    result = ctx.store.verify_product(ctx.db, sp)
    product.verification_passed = bool(result["passed"])
    product.verification_notes = result
    if not result["passed"]:
        product.status = ProductStatus.verification_failed
    ctx.db.flush()
    ctx.log(
        "verify_published_product",
        {"product_id": product_id},
        result,
        success=result["passed"],
        evidence="verification cart",
    )
    return result


def record_run_summary(summary: str, metrics_json: str = "{}") -> dict[str, Any]:
    """Persist a concise run summary of actual outcomes (not chain-of-thought)."""
    import json

    ctx = get_ctx()
    metrics = json.loads(metrics_json) if isinstance(metrics_json, str) else metrics_json
    row = RunSummary(
        id=uuid.uuid4(),
        batch_id=ctx.batch.id,
        job_id=ctx.job.id,
        summary=summary,
        metrics=metrics,
    )
    ctx.db.add(row)
    ctx.db.flush()
    out = {"summary_id": str(row.id)}
    ctx.log("record_run_summary", {"summary": summary}, out)
    return out


def run_deterministic_processing(
    ctx: ToolContext,
    *,
    enrich: bool = True,
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic parse/normalize/validate. Enrichment is optional (replay only by default)."""
    q = select(Product).where(Product.batch_id == ctx.batch.id)
    if product_ids:
        q = q.where(Product.id.in_([uuid.UUID(pid) for pid in product_ids]))
    products = ctx.db.scalars(q).all()
    originals = []
    for p in products:
        # use import-linked original from first version or rebuild from proposed empty
        if p.versions:
            originals.append(p.versions[0].original)
        else:
            originals.append({"sku": p.sku})

    # Build originals from a temporary attribute set during import
    from app.db.models import ImportRow

    rows = ctx.db.scalars(select(ImportRow).where(ImportRow.batch_id == ctx.batch.id)).all()
    product_originals: dict[uuid.UUID, dict] = {}
    fingerprints: dict[str, uuid.UUID] = {}
    exact_dups: dict[uuid.UUID, uuid.UUID] = {}
    sku_map: dict[str, list[uuid.UUID]] = {}

    from app.services.csv_import import apply_mapping, row_fingerprint

    mapping = ctx.batch.column_mapping or {}
    for row in rows:
        if row.is_malformed or not row.product_id:
            continue
        mapped = apply_mapping(row.raw, mapping)
        product_originals[row.product_id] = mapped
        fp = row_fingerprint(mapped)
        if fp in fingerprints and fingerprints[fp] != row.product_id:
            exact_dups[row.product_id] = fingerprints[fp]
        else:
            fingerprints[fp] = row.product_id
        sku_map.setdefault(mapped.get("sku") or "", []).append(row.product_id)

    med = median_prices(list(product_originals.values()))
    slugs: set[str] = set()
    processed = 0
    settings = __import__("app.config", fromlist=["get_settings"]).get_settings()
    fixtures = settings.fixtures_root
    from pathlib import Path

    if not fixtures.is_absolute():
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        fixtures = alt if alt.exists() else Path.cwd() / fixtures
    provider = get_provider(fixtures)
    budget = EnrichmentBudget(settings.lookup_budget_per_run)
    for p in products:
        original = product_originals.get(p.id)
        if not original:
            continue
        # skip if already has a current version from prior resume — still re-check pending
        if p.current_version_id and ctx.job.checkpoint.get("processed_ids", []) and str(p.id) in ctx.job.checkpoint.get(
            "processed_ids", []
        ):
            continue
        process_product(
            ctx.db,
            p,
            original,
            median_price=med,
            existing_slugs=slugs,
            sku_conflicts=sku_map,
            exact_dup_of=exact_dups.get(p.id),
        )
        if p.current_version_id:
            v = ctx.db.get(ProductVersion, p.current_version_id)
            if v and enrich:
                enrich_product(ctx.db, p, v, original, provider, budget)
                from app.services.manufacturer_recovery import retrieve_manufacturer_record

                if (original.get("brand") or "").lower().find("seiko") >= 0 or (original.get("model") or ""):
                    if str(original.get("brand") or "").lower().find("seiko") >= 0:
                        retrieve_manufacturer_record(ctx.db, p)
                refresh_product_readiness(ctx.db, p)
            elif v:
                refresh_product_readiness(ctx.db, p)
            if v and v.seo.get("url_slug"):
                slugs.add(v.seo["url_slug"])
        processed += 1
        checkpoint = dict(ctx.job.checkpoint or {})
        done = list(checkpoint.get("processed_ids", []))
        done.append(str(p.id))
        checkpoint["processed_ids"] = done
        ctx.job.checkpoint = checkpoint
        ctx.db.flush()

    inspect_batch(str(ctx.batch.id))
    pending = ctx.db.scalars(
        select(Decision).where(
            Decision.batch_id == ctx.batch.id, Decision.status == DecisionStatus.pending
        )
    ).all()
    return {"processed": processed, "pending_decisions": len(pending)}
