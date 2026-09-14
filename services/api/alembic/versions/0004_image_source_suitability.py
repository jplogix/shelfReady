"""Track image source, permitted usage, and category suitability."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_image_source"
down_revision: Union[str, None] = "0003_enrichment_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("source_kind", sa.String(50), server_default="unknown", nullable=False),
    )
    op.add_column(
        "product_images",
        sa.Column("usage_permission", sa.String(50), server_default="unknown", nullable=False),
    )
    op.add_column(
        "product_images",
        sa.Column("suitability", sa.String(50), server_default="unclassified", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("product_images", "suitability")
    op.drop_column("product_images", "usage_permission")
    op.drop_column("product_images", "source_kind")
