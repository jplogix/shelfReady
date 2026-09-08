from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProductStatus(str, enum.Enum):
    imported = "imported"
    processing = "processing"
    needs_review = "needs_review"
    ready = "ready"
    publishing = "publishing"
    published = "published"
    verification_failed = "verification_failed"
    failed = "failed"


class BatchStatus(str, enum.Enum):
    draft = "draft"
    importing = "importing"
    ready = "ready"
    processing = "processing"
    awaiting_decisions = "awaiting_decisions"
    publishing = "publishing"
    completed = "completed"
    failed = "failed"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    awaiting_decisions = "awaiting_decisions"
    completed = "completed"
    failed = "failed"


class DecisionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"


class DecisionKind(str, enum.Enum):
    missing_price = "missing_price"
    suspicious_price = "suspicious_price"
    conflicting_sku = "conflicting_sku"
    exact_duplicate = "exact_duplicate"
    ambiguous_category = "ambiguous_category"
    unknown_brand_alias = "unknown_brand_alias"
    unknown_color_alias = "unknown_color_alias"
    no_primary_image = "no_primary_image"
    unsupported_claim = "unsupported_claim"
    price_change = "price_change"
    inventory_change = "inventory_change"
    publication = "publication"
    other = "other"


class ImageClass(str, enum.Enum):
    product_only = "product_only"
    model_worn = "model_worn"
    detail = "detail"
    packaging = "packaging"
    unknown = "unknown"


class RuleScope(str, enum.Enum):
    workspace = "workspace"
    supplier = "supplier"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    auto_publish_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batches: Mapped[list[Batch]] = relationship(back_populates="workspace")
    products: Mapped[list[Product]] = relationship(back_populates="workspace")
    rules: Mapped[list[NormalizationRule]] = relationship(back_populates="workspace")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(200), default="Synthetic Supplier")
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status"), default=BatchStatus.draft, nullable=False
    )
    column_mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_filename: Mapped[Optional[str]] = mapped_column(String(500))
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="batches")
    import_rows: Mapped[list[ImportRow]] = relationship(back_populates="batch")
    products: Mapped[list[Product]] = relationship(back_populates="batch")
    jobs: Mapped[list[Job]] = relationship(back_populates="batch")


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_malformed: Mapped[bool] = mapped_column(Boolean, default=False)
    malformed_reason: Mapped[Optional[str]] = mapped_column(Text)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("products.id"))

    batch: Mapped[Batch] = relationship(back_populates="import_rows")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("batch_id", "sku", name="uq_batch_sku"),
        Index("ix_products_batch_status", "batch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status"), default=ProductStatus.imported, nullable=False
    )
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    approved_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    store_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    verification_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_notes: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="products")
    batch: Mapped[Batch] = relationship(back_populates="products")
    versions: Mapped[list[ProductVersion]] = relationship(
        back_populates="product", foreign_keys="ProductVersion.product_id"
    )
    images: Mapped[list[ProductImage]] = relationship(back_populates="product")
    decisions: Mapped[list[Decision]] = relationship(back_populates="product")


class ProductVersion(Base):
    __tablename__ = "product_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    proposed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seo: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    diffs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_publishable: Mapped[bool] = mapped_column(Boolean, default=False)
    blockers: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(back_populates="versions", foreign_keys=[product_id])


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    derivative_path: Mapped[Optional[str]] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    image_class: Mapped[ImageClass] = mapped_column(
        Enum(ImageClass, name="image_class"), default=ImageClass.unknown, nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    classification_source: Mapped[str] = mapped_column(String(50), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(back_populates="images")


class NormalizationRule(Base):
    __tablename__ = "normalization_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # brand|color|category|type
    source_value: Mapped[str] = mapped_column(String(300), nullable=False)
    target_value: Mapped[str] = mapped_column(String(300), nullable=False)
    scope: Mapped[RuleScope] = mapped_column(
        Enum(RuleScope, name="rule_scope"), default=RuleScope.workspace, nullable=False
    )
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="rules")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("products.id"))
    product_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("product_versions.id"))
    kind: Mapped[DecisionKind] = mapped_column(Enum(DecisionKind, name="decision_kind"), nullable=False)
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status"), default=DecisionStatus.pending, nullable=False
    )
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    original_value: Mapped[Optional[Any]] = mapped_column(JSONB)
    proposed_value: Mapped[Optional[Any]] = mapped_column(JSONB)
    edited_value: Mapped[Optional[Any]] = mapped_column(JSONB)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    consequence: Mapped[str] = mapped_column(Text, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(40), default="review")  # safe|review|approval
    bulk_key: Mapped[Optional[str]] = mapped_column(String(200))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Optional[Product]] = relationship(back_populates="decisions")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # process|publish|resume
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.pending, nullable=False
    )
    agent_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch: Mapped[Batch] = relationship(back_populates="jobs")
    actions: Mapped[list[AgentAction]] = relationship(back_populates="job")


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="actions")


class RunSummary(Base):
    __tablename__ = "run_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoreProduct(Base):
    __tablename__ = "store_products"
    __table_args__ = (UniqueConstraint("workspace_id", "external_id", name="uq_store_external"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)  # stable publish id
    slug: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    brand: Mapped[Optional[str]] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_image_path: Mapped[Optional[str]] = mapped_column(String(1000))
    images: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    seo: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    json_ld: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    variant_sku: Mapped[str] = mapped_column(String(120), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), default="operator")  # operator|verification
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[CartItem]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "store_product_id", name="uq_cart_item"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id"), nullable=False)
    store_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store_products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")
