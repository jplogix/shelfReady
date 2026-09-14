from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModeResponse(BaseModel):
    agent_mode: str
    lookup_mode: str
    label: str
    is_replay: bool
    is_live: bool
    lookup_is_replay: bool


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    auto_publish_demo: bool
    currency: str

    model_config = {"from_attributes": True}


class WorkspaceUpdate(BaseModel):
    auto_publish_demo: Optional[bool] = None
    name: Optional[str] = None


class ColumnMapping(BaseModel):
    mapping: dict[str, Optional[str]]
    headers: list[str]
    preview_rows: list[dict[str, Any]]


class BatchCreate(BaseModel):
    name: str = "Supplier import"
    supplier_name: str = "Synthetic Supplier"


class BatchOut(BaseModel):
    id: uuid.UUID
    name: str
    supplier_name: str
    status: str
    batch_kind: str = "import"
    column_mapping: dict[str, Any]
    source_filename: Optional[str]
    counts: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(default_factory=list)
    verify: bool = True


class ProductOut(BaseModel):
    id: uuid.UUID
    sku: str
    supplier_sku: Optional[str] = None
    title: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = "USD"
    status: str
    readiness: Optional[str] = None
    verification_passed: bool
    current_version_id: Optional[uuid.UUID]
    approved_version_id: Optional[uuid.UUID]
    store_product_id: Optional[uuid.UUID]
    store_slug: Optional[str] = None
    thumbnail: Optional[str] = None
    issue_count: int = 0
    enrichment_summary: Optional[str] = None
    next_action: Optional[str] = None
    is_publishable: bool = False

    model_config = {"from_attributes": True}


class FieldEvidenceOut(BaseModel):
    id: uuid.UUID
    field_name: str
    original_supplier_value: Any = None
    proposed_value: Any = None
    source_provider: str
    source_url: Optional[str] = None
    lookup_identifier: Optional[str] = None
    match_outcome: str
    match_explanation: str
    acceptance_status: str
    is_cached: bool = False
    is_replay: bool = False

    model_config = {"from_attributes": True}


class ProductDetail(ProductOut):
    original: Optional[dict[str, Any]] = None
    proposed: Optional[dict[str, Any]] = None
    seo: Optional[dict[str, Any]] = None
    diffs: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    images: list[dict[str, Any]] = Field(default_factory=list)
    is_publishable: bool = False
    import_row_number: Optional[int] = None
    field_evidence: list[FieldEvidenceOut] = Field(default_factory=list)
    decisions: list["DecisionOut"] = Field(default_factory=list)


class StartProcessRequest(BaseModel):
    column_mapping: dict[str, Optional[str]]


class DecisionOut(BaseModel):
    id: uuid.UUID
    product_id: Optional[uuid.UUID]
    product_version_id: Optional[uuid.UUID]
    kind: str
    status: str
    field_name: Optional[str]
    original_value: Any
    proposed_value: Any
    edited_value: Any = None
    evidence: dict[str, Any]
    reason: str
    consequence: str
    risk_tier: str
    bulk_key: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionResolve(BaseModel):
    action: str  # approve | edit | reject
    edited_value: Any = None
    save_as_rule: bool = False
    rule_type: Optional[str] = None
    rule_target: Optional[str] = None


class BulkDecisionResolve(BaseModel):
    decision_ids: list[uuid.UUID]
    action: str = "approve"


class JobOut(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    job_type: str
    status: str
    agent_mode: str
    checkpoint: dict[str, Any]
    error: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentActionOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    tool_name: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    success: bool
    evidence_summary: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreImageOut(BaseModel):
    path: str
    alt: Optional[str] = None
    is_primary: bool = False
    source_kind: Optional[str] = None
    usage_permission: Optional[str] = None
    suitability: Optional[str] = None
    caption: Optional[str] = None


class StoreProductOut(BaseModel):
    """Approved storefront fields only — no operator or unpublished data."""

    id: uuid.UUID
    slug: str
    title: str
    description: Optional[str]
    brand: Optional[str]
    price: Decimal
    currency: str
    stock: int
    available: bool
    primary_image_path: Optional[str]
    images: list[StoreImageOut]
    sku: str
    image_caption: Optional[str] = None
    image_suitability: Optional[str] = None
    specifications: list[dict[str, str]] = Field(default_factory=list)
    collection: Optional[str] = None

    model_config = {"from_attributes": True}


class ListingFieldOut(BaseModel):
    field: str
    label: str
    value: Any = None


class ListingCorrectionOut(BaseModel):
    field: str
    label: str
    original: Any = None
    accepted: Any = None


class ListingEvidenceOut(BaseModel):
    field_name: str
    label: str
    original_supplier_value: Any = None
    proposed_value: Any = None
    source_provider: str
    source_url: Optional[str] = None
    match_outcome: str
    match_explanation: str
    is_replay: bool = False


class ListingAssessmentOut(BaseModel):
    match_outcome: str
    explanation: str
    recommended_action: Optional[str] = None
    agreements: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class ListingProvenanceOut(BaseModel):
    slug: str
    title: str
    preparation_label: str
    agent_mode: str
    lookup_mode: str
    original_row: dict[str, Any]
    original_fields: list[ListingFieldOut] = Field(default_factory=list)
    corrections: list[ListingCorrectionOut]
    evidence: list[ListingEvidenceOut]
    assessment: Optional[ListingAssessmentOut] = None
    image_caption: Optional[str] = None
    image_suitability: Optional[str] = None
    outcome_summary: Optional[str] = None


class CartItemOut(BaseModel):
    id: uuid.UUID
    store_product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    currency: str
    title: Optional[str] = None
    slug: Optional[str] = None
    image: Optional[str] = None
    available: bool = True
    stock: int = 0
    line_total: Decimal = Decimal("0")


class CartOut(BaseModel):
    id: uuid.UUID
    purpose: str
    items: list[CartItemOut]
    subtotal: Decimal = Decimal("0")
    currency: str = "USD"
    item_count: int = 0


class AddToCartRequest(BaseModel):
    store_product_id: uuid.UUID
    quantity: int = 1
    purpose: str = "shopper"


class UpdateCartItemRequest(BaseModel):
    quantity: int
