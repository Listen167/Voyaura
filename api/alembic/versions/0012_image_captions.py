"""Add deterministic travel caption snapshots.

Revision ID: 0012_image_captions
Revises: 0011_image_recipes
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_image_captions"
down_revision: str | None = "0011_image_recipes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column(
            "caption_mode",
            sa.String(length=24),
            server_default="none",
            nullable=False,
        ),
    )
    op.add_column(
        "image_generation_jobs",
        sa.Column("caption_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "caption_snapshot")
    op.drop_column("image_generation_jobs", "caption_mode")
