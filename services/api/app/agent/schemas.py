"""Focused Strands structured-output schemas. One product or task per invocation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MatchOutcomeLabel(str, Enum):
    matching_evidence = "matching_evidence"
    possible_match = "possible_match"
    conflicting_evidence = "conflicting_evidence"
    no_match = "no_match"
    invalid_identifier = "invalid_identifier"
    lookup_unavailable = "lookup_unavailable"
    no_lookup = "no_lookup"
    skipped_complete = "skipped_complete"


class AttributeFinding(BaseModel):
    field_name: str = Field(description="Product field this finding refers to")
    supplier_value: Any = Field(default=None, description="Value from the supplier row")
    evidence_value: Any = Field(default=None, description="Value from referenced evidence")
    evidence_ids: list[str] = Field(default_factory=list, description="Existing FieldEvidence IDs only")


class ProductAssessment(BaseModel):
    """Merchant-facing assessment for a single product after inspecting evidence."""

    candidate_identifier: str | None = Field(
        default=None,
        description="Normalized barcode/GTIN if one exists; null when unmatched or absent",
    )
    match_outcome: MatchOutcomeLabel = Field(description="Overall identity/evidence outcome")
    attribute_agreements: list[AttributeFinding] = Field(default_factory=list)
    attribute_conflicts: list[AttributeFinding] = Field(default_factory=list)
    missing_information: list[str] = Field(
        default_factory=list,
        description="Required or important fields still unknown",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="FieldEvidence IDs that were actually retrieved for this product",
    )
    explanation: str = Field(description="Concise merchant-facing explanation")
    needs_merchant_decision: bool = Field(
        default=False,
        description="True when a human must choose among contradictions or supply a required value",
    )
    recommended_action: Literal[
        "none",
        "lookup",
        "request_decision",
        "propose_patch",
        "draft_listing",
    ] = Field(
        default="none",
        description="Next application action justified by the evidence",
    )


ALLOWLISTED_PATCH_FIELDS = Literal[
    "title",
    "description",
    "brand",
    "category",
    "color",
    "color_families",
    "size",
    "model",
    "product_type",
]


class ProductPatchProposal(BaseModel):
    """A single allowlisted field change. Forbidden fields must not appear."""

    field: ALLOWLISTED_PATCH_FIELDS
    proposed_value: str | int | float | list[str] | None = Field(
        description="Typed proposed value, or null when unresolved/unknown"
    )
    unresolved: bool = Field(
        default=False,
        description="True when the value is unknown and must remain unresolved",
    )
    evidence_references: list[str] = Field(default_factory=list)
    explanation: str


class ListingDraft(BaseModel):
    """Storefront copy grounded in accepted facts only."""

    title: str
    description: str
    feature_bullets: list[str] = Field(default_factory=list)
    seo_title: str
    meta_description: str
    supporting_fact_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs or accepted fact keys that support the claims",
    )
