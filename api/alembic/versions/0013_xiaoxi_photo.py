"""Add Xiaoxi photo composition snapshots.

Revision ID: 0013_xiaoxi_photo
Revises: 0012_image_captions
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_xiaoxi_photo"
down_revision: str | None = "0012_image_captions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column("companion_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "companion_snapshot")
