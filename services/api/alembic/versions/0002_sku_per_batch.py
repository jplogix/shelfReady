"""Relax SKU uniqueness to per-batch for demo reloads."""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_sku_per_batch"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_workspace_sku", "products", type_="unique")
    op.create_unique_constraint("uq_batch_sku", "products", ["batch_id", "sku"])


def downgrade() -> None:
    op.drop_constraint("uq_batch_sku", "products", type_="unique")
    op.create_unique_constraint("uq_workspace_sku", "products", ["workspace_id", "sku"])
