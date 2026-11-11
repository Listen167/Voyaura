"""Add city visit source.

Revision ID: 0003_check_in_source
Revises: 0002_city_memories
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_check_in_source"
down_revision: str | None = "0002_city_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "city_visits",
        sa.Column(
            "check_in_source",
            sa.String(length=20),
            nullable=False,
            server_default="device",
        ),
    )
    op.alter_column("city_visits", "check_in_source", server_default=None)


def downgrade() -> None:
    op.drop_column("city_visits", "check_in_source")
