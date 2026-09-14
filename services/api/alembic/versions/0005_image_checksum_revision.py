"""Bind images to revisions and store checksums."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_image_checksum"
down_revision: Union[str, None] = "0004_image_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_images", sa.Column("checksum_sha256", sa.String(64), nullable=True))
    op.add_column("product_images", sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_images", sa.Column("source_url", sa.String(1000), nullable=True))
    op.add_column("product_images", sa.Column("match_rationale", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_images", "match_rationale")
    op.drop_column("product_images", "source_url")
    op.drop_column("product_images", "product_version_id")
    op.drop_column("product_images", "checksum_sha256")
