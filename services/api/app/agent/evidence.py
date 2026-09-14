"""Validate structured agent output against persisted evidence and policy."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.schemas import ListingDraft, ProductAssessment, ProductPatchProposal
from app.db.models import FieldEvidence, MatchOutcome, Product, ProductVersion

FORBIDDEN_AUTOFILL_FIELDS = frozenset(
    {
        "price",
        "stock",
        "currency",
        "gtin",
        "upc",
        "ean",
        "sku",
        "identifier_raw",
        "identifier_normalized",
        "certification",
        "certifications",
        "authenticity",
        "authentic",
    }
)

ALLOWLISTED_FIELDS = frozenset(
    {
        "title",
        "description",
        "brand",
        "category",
        "color",
        "color_families",
        "size",
        "model",
        "product_type",
    }
)

REQUIRED_UNRESOLVED_FIELDS = frozenset({"price", "sku", "title"})


class EvidenceValidationError(ValueError):
    """Structured output failed application-level evidence checks."""


def _as_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise EvidenceValidationError(f"invalid_evidence_id:{value}") from exc


def load_evidence_map(db: Session, product_id: uuid.UUID) -> dict[str, FieldEvidence]:
    rows = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product_id)).all()
    return {str(row.id): row for row in rows}


def validate_evidence_ids(
    db: Session,
    product: Product,
    evidence_ids: list[str],
    *,
    expected_version_id: uuid.UUID | None = None,
) -> list[FieldEvidence]:
    if not evidence_ids:
        return []
    found: list[FieldEvidence] = []
    seen: set[str] = set()
    for raw in evidence_ids:
        if raw in seen:
            continue
        seen.add(raw)
        ev_id = _as_uuid(raw)
        row = db.get(FieldEvidence, ev_id)
        if row is None:
            raise EvidenceValidationError(f"unknown_evidence:{raw}")
        if row.product_id != product.id:
            raise EvidenceValidationError(f"unrelated_evidence:{raw}")
        if expected_version_id and row.product_version_id != expected_version_id:
            raise EvidenceValidationError(f"stale_evidence_revision:{raw}")
        found.append(row)
    return found


def assert_current_revision(product: Product, expected_version_id: uuid.UUID | None) -> ProductVersion:
    if not product.current_version_id:
        raise EvidenceValidationError("missing_current_revision")
    if expected_version_id and product.current_version_id != expected_version_id:
        raise EvidenceValidationError("stale_product_revision")
    return product  # type: ignore[return-value]


def validate_assessment(
    db: Session,
    product: Product,
    version: ProductVersion,
    assessment: ProductAssessment,
) -> ProductAssessment:
    """Schema-valid is not enough — referenced evidence must exist and belong here."""
    validate_evidence_ids(
        db,
        product,
        assessment.evidence_references,
        expected_version_id=version.id,
    )
    for finding in [*assessment.attribute_agreements, *assessment.attribute_conflicts]:
        validate_evidence_ids(db, product, finding.evidence_ids, expected_version_id=version.id)
    return assessment


def validate_patch_proposal(
    db: Session,
    product: Product,
    version: ProductVersion,
    proposal: ProductPatchProposal,
    *,
    expected_version_id: uuid.UUID | None = None,
) -> None:
    target = expected_version_id or version.id
    if product.current_version_id != target:
        raise EvidenceValidationError("stale_product_revision")
    field = str(proposal.field)
    if field in FORBIDDEN_AUTOFILL_FIELDS:
        raise EvidenceValidationError(f"forbidden_field:{field}")
    if field not in ALLOWLISTED_FIELDS:
        raise EvidenceValidationError(f"field_not_allowed:{field}")
    if proposal.unresolved:
        if proposal.proposed_value not in (None, "", []):
            raise EvidenceValidationError("unresolved_must_not_carry_value")
        return
    if proposal.proposed_value is None:
        raise EvidenceValidationError("missing_proposed_value")
    if field == "color_families" and not isinstance(proposal.proposed_value, list):
        raise EvidenceValidationError("color_families_must_be_list")
    if field != "color_families" and isinstance(proposal.proposed_value, list):
        raise EvidenceValidationError(f"unexpected_list_value:{field}")
    refs = validate_evidence_ids(db, product, proposal.evidence_references, expected_version_id=version.id)
    if not refs:
        raise EvidenceValidationError("proposal_requires_evidence")
    # Existence is not support. Require at least one non-conflicting row for the field.
    supporting = [
        ev
        for ev in refs
        if ev.field_name in {field, "title", "brand", "model", "size", "color"}
        and ev.match_outcome
        in {MatchOutcome.matching_evidence, MatchOutcome.possible_match}
    ]
    conflicting = [ev for ev in refs if ev.match_outcome == MatchOutcome.conflicting_evidence]
    if conflicting and not supporting:
        raise EvidenceValidationError("contradictory_evidence_unresolved")
    if not supporting:
        raise EvidenceValidationError("evidence_does_not_support_claim")


def validate_listing_draft(
    db: Session,
    product: Product,
    version: ProductVersion,
    draft: ListingDraft,
) -> None:
    validate_evidence_ids(db, product, draft.supporting_fact_ids, expected_version_id=version.id)
    blocked = ("certified", "authentic", "genuine", "organic certified", "fda approved")
    blob = " ".join(
        [draft.title, draft.description, draft.seo_title, draft.meta_description, *draft.feature_bullets]
    ).lower()
    if any(term in blob for term in blocked):
        raise EvidenceValidationError("listing_contains_authenticity_or_certification_claim")


def contradictions_remain_visible(db: Session, product: Product) -> list[FieldEvidence]:
    return list(
        db.scalars(
            select(FieldEvidence).where(
                FieldEvidence.product_id == product.id,
                FieldEvidence.match_outcome == MatchOutcome.conflicting_evidence,
            )
        ).all()
    )


def required_unknowns(version: ProductVersion) -> list[str]:
    proposed = dict(version.proposed or {})
    missing: list[str] = []
    for field in REQUIRED_UNRESOLVED_FIELDS:
        if proposed.get(field) in (None, ""):
            missing.append(field)
    return missing
