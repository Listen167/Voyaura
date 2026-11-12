"""Add reproducible image recipes and source preservation.

Revision ID: 0011_image_recipes
Revises: 0010_image_studio
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_image_recipes"
down_revision: str | None = "0010_image_studio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column(
            "preservation_level",
            sa.String(length=20),
            server_default="balanced",
            nullable=False,
        ),
    )
    op.add_column(
        "image_generation_jobs",
        sa.Column(
            "recipe_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "recipe_snapshot")
    op.drop_column("image_generation_jobs", "preservation_level")
