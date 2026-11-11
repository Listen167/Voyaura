"""Add idempotent media management operations.

Revision ID: 0008_media_management
Revises: 0007_media_processing
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_media_management"
down_revision: str | None = "0007_media_processing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_mutations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("target_memory_id", sa.Uuid(), nullable=False),
        sa.Column("target_asset_id", sa.Uuid(), nullable=False),
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
            name="uq_media_mutation_user_request",
        ),
    )
    op.create_index(
        op.f("ix_media_mutations_target_memory_id"),
        "media_mutations",
        ["target_memory_id"],
    )
    op.create_index(
        op.f("ix_media_mutations_target_asset_id"),
        "media_mutations",
        ["target_asset_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_media_mutations_target_asset_id"), table_name="media_mutations")
    op.drop_index(op.f("ix_media_mutations_target_memory_id"), table_name="media_mutations")
    op.drop_table("media_mutations")
