from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModeResponse(BaseModel):
    agent_mode: str
    label: str
    is_replay: bool
    is_live: bool


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
    column_mapping: dict[str, Any]
    source_filename: Optional[str]
    counts: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class StartProcessRequest(BaseModel):
    column_mapping: dict[str, Optional[str]]


class ProductOut(BaseModel):
    id: uuid.UUID
    sku: str
    status: str
    verification_passed: bool
    current_version_id: Optional[uuid.UUID]
    approved_version_id: Optional[uuid.UUID]
    store_product_id: Optional[uuid.UUID]

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


class StoreProductOut(BaseModel):
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
    images: list[Any]
    seo: dict[str, Any]
    json_ld: dict[str, Any]
    variant_sku: str
    external_id: str

    model_config = {"from_attributes": True}


class CartItemOut(BaseModel):
    id: uuid.UUID
    store_product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    currency: str
    title: Optional[str] = None


class CartOut(BaseModel):
    id: uuid.UUID
    purpose: str
    items: list[CartItemOut]


class AddToCartRequest(BaseModel):
    store_product_id: uuid.UUID
    quantity: int = 1
    purpose: str = "operator"
