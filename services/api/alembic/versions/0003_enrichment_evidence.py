"""Field evidence, lookup cache, product readiness, batch kind."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_enrichment_evidence"
down_revision: Union[str, None] = "0002_sku_per_batch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

match_outcome_enum = postgresql.ENUM(
    "matching_evidence",
    "possible_match",
    "conflicting_evidence",
    "no_match",
    "invalid_identifier",
    "lookup_unavailable",
    name="match_outcome",
    create_type=False,
)
evidence_acceptance_enum = postgresql.ENUM(
    "pending", "accepted", "rejected", name="evidence_acceptance", create_type=False
)
product_readiness_enum = postgresql.ENUM(
    "ready_to_publish",
    "needs_information",
    "has_conflicts",
    "published",
    name="product_readiness",
    create_type=False,
)
batch_kind_enum = postgresql.ENUM("stress_test", "demo", "import", name="batch_kind", create_type=False)


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN CREATE TYPE product_readiness AS ENUM ("
        "'ready_to_publish', 'needs_information', 'has_conflicts', 'published');"
        " EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE batch_kind AS ENUM ('stress_test', 'demo', 'import');"
        " EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE match_outcome AS ENUM ("
        "'matching_evidence', 'possible_match', 'conflicting_evidence', "
        "'no_match', 'invalid_identifier', 'lookup_unavailable');"
        " EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE evidence_acceptance AS ENUM ('pending', 'accepted', 'rejected');"
        " EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )

    for kind in ("conflicting_variant", "confirm_product_match", "accept_enrichment"):
        op.execute(f"ALTER TYPE decision_kind ADD VALUE IF NOT EXISTS '{kind}'")

    conn = op.get_bind()
    insp = sa.inspect(conn)
    batch_cols = {c["name"] for c in insp.get_columns("batches")}
    product_cols = {c["name"] for c in insp.get_columns("products")}

    if "batch_kind" not in batch_cols:
        op.add_column(
            "batches",
            sa.Column("batch_kind", batch_kind_enum, server_default="import", nullable=False),
        )
    if "supplier_sku" not in product_cols:
        op.add_column("products", sa.Column("supplier_sku", sa.String(120), nullable=True))
    if "readiness" not in product_cols:
        op.add_column("products", sa.Column("readiness", product_readiness_enum, nullable=True))
    if "store_slug" not in product_cols:
        op.add_column("products", sa.Column("store_slug", sa.String(300), nullable=True))

    if "lookup_cache" not in insp.get_table_names():
        op.create_table(
            "lookup_cache",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("normalized_query", sa.String(200), nullable=False),
            sa.Column("response", postgresql.JSONB(), server_default="{}", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("provider", "normalized_query", name="uq_lookup_cache"),
        )

    if "field_evidence" not in insp.get_table_names():
        op.create_table(
            "field_evidence",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
            sa.Column(
                "product_version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("product_versions.id"),
                nullable=False,
            ),
            sa.Column("field_name", sa.String(100), nullable=False),
            sa.Column("original_supplier_value", postgresql.JSONB(), nullable=True),
            sa.Column("proposed_value", postgresql.JSONB(), nullable=True),
            sa.Column("source_provider", sa.String(50), nullable=False),
            sa.Column("source_url", sa.String(1000), nullable=True),
            sa.Column("provider_record_id", sa.String(200), nullable=True),
            sa.Column("lookup_identifier", sa.String(200), nullable=True),
            sa.Column("lookup_query", sa.String(200), nullable=True),
            sa.Column("match_outcome", match_outcome_enum, nullable=False),
            sa.Column("match_explanation", sa.Text(), nullable=False),
            sa.Column(
                "acceptance_status",
                evidence_acceptance_enum,
                server_default="pending",
                nullable=False,
            ),
            sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("is_cached", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("is_replay", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("raw_response", postgresql.JSONB(), server_default="{}", nullable=False),
        )
        op.create_index("ix_field_evidence_product", "field_evidence", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_field_evidence_product", table_name="field_evidence")
    op.drop_table("field_evidence")
    op.drop_table("lookup_cache")
    op.drop_column("products", "store_slug")
    op.drop_column("products", "readiness")
    op.drop_column("products", "supplier_sku")
    op.drop_column("batches", "batch_kind")
    op.execute("DROP TYPE IF EXISTS evidence_acceptance")
    op.execute("DROP TYPE IF EXISTS match_outcome")
    op.execute("DROP TYPE IF EXISTS batch_kind")
    op.execute("DROP TYPE IF EXISTS product_readiness")
