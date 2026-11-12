"""Add image studio favorites and idempotent deletion.

Revision ID: 0010_image_studio
Revises: 0009_image_generation
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_image_studio"
down_revision: str | None = "0009_image_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "image_job_mutations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_job_id", sa.Uuid(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "client_request_id",
            name="uq_image_job_mutation_user_request",
        ),
    )
    op.create_index(
        op.f("ix_image_job_mutations_target_job_id"),
        "image_job_mutations",
        ["target_job_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_image_job_mutations_target_job_id"), table_name="image_job_mutations")
    op.drop_table("image_job_mutations")
    op.drop_column("image_generation_jobs", "is_favorite")
