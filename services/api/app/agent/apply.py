"""Consume validated structured output into product versions, evidence, and decisions."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.evidence import (
    contradictions_remain_visible,
    required_unknowns,
    validate_assessment,
    validate_listing_draft,
    validate_patch_proposal,
)
from app.agent.schemas import ListingDraft, ProductAssessment, ProductPatchProposal
from app.db.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    EvidenceAcceptance,
    FieldEvidence,
    Product,
    ProductStatus,
    ProductVersion,
)
from app.policy.readiness import refresh_product_readiness


def store_assessment(
    db: Session,
    product: Product,
    version: ProductVersion,
    assessment: ProductAssessment,
    *,
    run_id: uuid.UUID,
) -> ProductAssessment:
    validated = validate_assessment(db, product, version, assessment)
    provenance = dict(version.provenance or {})
    provenance["assessment"] = {
        **validated.model_dump(mode="json"),
        "product_id": str(product.id),
        "run_id": str(run_id),
        "revision_id": str(version.id),
    }
    version.provenance = provenance

    for ev_id in validated.evidence_references:
        ev = db.get(FieldEvidence, uuid.UUID(ev_id))
        if ev and ev.acceptance_status == EvidenceAcceptance.pending:
            if ev.field_name in {f.field_name for f in validated.attribute_agreements}:
                ev.acceptance_status = EvidenceAcceptance.accepted

    if validated.attribute_conflicts or validated.match_outcome.value == "conflicting_evidence":
        _ensure_conflict_decision(db, product, version, validated)
    if validated.needs_merchant_decision and validated.missing_information:
        _ensure_missing_decisions(db, product, version, validated)

    if contradictions_remain_visible(db, product) or required_unknowns(version):
        product.status = ProductStatus.needs_review
        version.is_publishable = False
    refresh_product_readiness(db, product)
    db.flush()
    return validated


def apply_patch_proposal(
    db: Session,
    product: Product,
    version: ProductVersion,
    proposal: ProductPatchProposal,
    *,
    expected_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    validate_patch_proposal(
        db, product, version, proposal, expected_version_id=expected_version_id or version.id
    )
    if proposal.unresolved:
        return {"applied": False, "unresolved": True, "field": proposal.field}

    proposed = dict(version.proposed)
    field = str(proposal.field)
    if field == "color":
        proposed["color_label"] = proposal.proposed_value
    else:
        proposed[field] = proposal.proposed_value
    next_version = ProductVersion(
        id=uuid.uuid4(),
        product_id=product.id,
        version_number=version.version_number + 1,
        original=version.original,
        proposed=proposed,
        seo=version.seo,
        diffs=[{"field": field, "original": version.proposed.get(field), "proposed": proposal.proposed_value}],
        provenance={**dict(version.provenance), "patch": "structured_proposal", "explanation": proposal.explanation},
        is_publishable=False,
        blockers=version.blockers,
    )
    db.add(next_version)
    db.flush()
    product.current_version_id = next_version.id
    product.approved_version_id = None
    refresh_product_readiness(db, product)
    db.flush()
    return {
        "applied": True,
        "field": field,
        "version_id": str(next_version.id),
        "unresolved": False,
    }


def apply_listing_draft(
    db: Session,
    product: Product,
    version: ProductVersion,
    draft: ListingDraft,
) -> dict[str, Any]:
    validate_listing_draft(db, product, version, draft)
    seo = dict(version.seo or {})
    seo.update(
        {
            "product_title": draft.title,
            "short_description": draft.description,
            "page_title": draft.seo_title[:60],
            "meta_description": draft.meta_description[:155],
            "feature_bullets": draft.feature_bullets,
            "source": "structured_listing_draft",
            "supporting_fact_ids": draft.supporting_fact_ids,
            "noindex": True,
        }
    )
    version.seo = seo
    proposed = dict(version.proposed)
    if draft.title and not proposed.get("title"):
        proposed["title"] = draft.title
    if draft.description and not proposed.get("description"):
        proposed["description"] = draft.description
    version.proposed = proposed
    db.flush()
    return {"applied": True, "seo_title": seo["page_title"]}


def _ensure_conflict_decision(
    db: Session,
    product: Product,
    version: ProductVersion,
    assessment: ProductAssessment,
) -> None:
    existing = db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.kind == DecisionKind.conflicting_variant,
            Decision.status == DecisionStatus.pending,
        )
    ).first()
    if existing:
        return
    conflict = assessment.attribute_conflicts[0] if assessment.attribute_conflicts else None
    db.add(
        Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=DecisionKind.conflicting_variant,
            status=DecisionStatus.pending,
            field_name=conflict.field_name if conflict else "variant",
            original_value=conflict.supplier_value if conflict else None,
            proposed_value=conflict.evidence_value if conflict else None,
            evidence={
                "assessment": assessment.explanation,
                "evidence_ids": assessment.evidence_references,
                "conflicts": [c.model_dump(mode="json") for c in assessment.attribute_conflicts],
            },
            reason=assessment.explanation or "Evidence conflicts with the supplier record.",
            consequence="Choose the correct variant or keep unresolved. Publication stays blocked.",
            risk_tier="approval",
        )
    )
    product.status = ProductStatus.needs_review
    version.is_publishable = False


def _ensure_missing_decisions(
    db: Session,
    product: Product,
    version: ProductVersion,
    assessment: ProductAssessment,
) -> None:
    for field in assessment.missing_information:
        if field not in {"price"}:
            continue
        existing = db.scalars(
            select(Decision).where(
                Decision.product_id == product.id,
                Decision.kind == DecisionKind.missing_price,
                Decision.status == DecisionStatus.pending,
            )
        ).first()
        if existing:
            continue
        db.add(
            Decision(
                id=uuid.uuid4(),
                workspace_id=product.workspace_id,
                batch_id=product.batch_id,
                product_id=product.id,
                product_version_id=version.id,
                kind=DecisionKind.missing_price,
                status=DecisionStatus.pending,
                field_name="price",
                original_value=None,
                proposed_value=None,
                evidence={"assessment": assessment.explanation},
                reason="Required price is still unknown. The agent will not invent one.",
                consequence="Enter a price to continue. Approving without a value is not allowed.",
                risk_tier="approval",
            )
        )
