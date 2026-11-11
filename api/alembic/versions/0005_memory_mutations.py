"""Add idempotent memory mutation records.

Revision ID: 0005_memory_mutations
Revises: 0004_memory_idempotency
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_memory_mutations"
down_revision: str | None = "0004_memory_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_mutations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("target_memory_id", sa.Uuid(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "client_request_id",
            name="uq_memory_mutation_user_request",
        ),
    )
    op.create_index(
        op.f("ix_memory_mutations_target_memory_id"),
        "memory_mutations",
        ["target_memory_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_memory_mutations_target_memory_id"),
        table_name="memory_mutations",
    )
    op.drop_table("memory_mutations")
