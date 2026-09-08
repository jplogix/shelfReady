"""Initial schema for ShelfReady."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("auto_publish_demo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("supplier_name", sa.String(200), server_default="Synthetic Supplier"),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "importing",
                "ready",
                "processing",
                "awaiting_decisions",
                "publishing",
                "completed",
                "failed",
                name="batch_status",
            ),
            nullable=False,
        ),
        sa.Column("column_mapping", postgresql.JSONB(), server_default="{}"),
        sa.Column("source_filename", sa.String(500)),
        sa.Column("counts", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("sku", sa.String(120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "imported",
                "processing",
                "needs_review",
                "ready",
                "publishing",
                "published",
                "verification_failed",
                "failed",
                name="product_status",
            ),
            nullable=False,
        ),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("approved_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("store_product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("verification_passed", sa.Boolean(), server_default="false"),
        sa.Column("verification_notes", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "sku", name="uq_workspace_sku"),
    )
    op.create_index("ix_products_batch_status", "products", ["batch_id", "status"])
    op.create_table(
        "import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column("is_malformed", sa.Boolean(), server_default="false"),
        sa.Column("malformed_reason", sa.Text()),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
    )
    op.create_table(
        "product_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original", postgresql.JSONB(), nullable=False),
        sa.Column("proposed", postgresql.JSONB(), nullable=False),
        sa.Column("seo", postgresql.JSONB(), server_default="{}"),
        sa.Column("diffs", postgresql.JSONB(), server_default="[]"),
        sa.Column("provenance", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_publishable", sa.Boolean(), server_default="false"),
        sa.Column("blockers", postgresql.JSONB(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "product_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("original_path", sa.String(1000), nullable=False),
        sa.Column("derivative_path", sa.String(1000)),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("size_bytes", sa.Integer(), server_default="0"),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column(
            "image_class",
            sa.Enum("product_only", "model_worn", "detail", "packaging", "unknown", name="image_class"),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("classification_source", sa.String(50), server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "normalization_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("source_value", sa.String(300), nullable=False),
        sa.Column("target_value", sa.String(300), nullable=False),
        sa.Column("scope", sa.Enum("workspace", "supplier", name="rule_scope"), nullable=False),
        sa.Column("supplier_name", sa.String(200)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_versions.id")),
        sa.Column(
            "kind",
            sa.Enum(
                "missing_price",
                "suspicious_price",
                "conflicting_sku",
                "exact_duplicate",
                "ambiguous_category",
                "unknown_brand_alias",
                "unknown_color_alias",
                "no_primary_image",
                "unsupported_claim",
                "price_change",
                "inventory_change",
                "publication",
                "other",
                name="decision_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "edited", "rejected", name="decision_status"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(100)),
        sa.Column("original_value", postgresql.JSONB()),
        sa.Column("proposed_value", postgresql.JSONB()),
        sa.Column("edited_value", postgresql.JSONB()),
        sa.Column("evidence", postgresql.JSONB(), server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("consequence", sa.Text(), nullable=False),
        sa.Column("risk_tier", sa.String(40), server_default="review"),
        sa.Column("bulk_key", sa.String(200)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "awaiting_decisions", "completed", "failed", name="job_status"),
            nullable=False,
        ),
        sa.Column("agent_mode", sa.String(20), nullable=False),
        sa.Column("checkpoint", postgresql.JSONB(), server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("output_payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("success", sa.Boolean(), server_default="true"),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "run_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "store_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("brand", sa.String(200)),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("available", sa.Boolean(), server_default="true"),
        sa.Column("primary_image_path", sa.String(1000)),
        sa.Column("images", postgresql.JSONB(), server_default="[]"),
        sa.Column("seo", postgresql.JSONB(), server_default="{}"),
        sa.Column("json_ld", postgresql.JSONB(), server_default="{}"),
        sa.Column("variant_sku", sa.String(120), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_store_external"),
    )
    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("purpose", sa.String(40), server_default="operator"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column(
            "store_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("store_products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.UniqueConstraint("cart_id", "store_product_id", name="uq_cart_item"),
    )


def downgrade() -> None:
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("store_products")
    op.drop_table("run_summaries")
    op.drop_table("agent_actions")
    op.drop_table("jobs")
    op.drop_table("decisions")
    op.drop_table("normalization_rules")
    op.drop_table("product_images")
    op.drop_table("product_versions")
    op.drop_table("import_rows")
    op.drop_index("ix_products_batch_status", table_name="products")
    op.drop_table("products")
    op.drop_table("batches")
    op.drop_table("workspaces")
    for name in (
        "batch_status",
        "product_status",
        "image_class",
        "rule_scope",
        "decision_kind",
        "decision_status",
        "job_status",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
