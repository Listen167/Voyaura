"""Add memory idempotency key.

Revision ID: 0004_memory_idempotency
Revises: 0003_check_in_source
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_memory_idempotency"
down_revision: str | None = "0003_check_in_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("city_memories", sa.Column("client_request_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        "uq_city_memory_user_request",
        "city_memories",
        ["user_id", "client_request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_city_memory_user_request", "city_memories", type_="unique")
    op.drop_column("city_memories", "client_request_id")
