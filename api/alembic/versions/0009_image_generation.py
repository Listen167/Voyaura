"""Add private image generation jobs.

Revision ID: 0009_image_generation
Revises: 0008_media_management
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_image_generation"
down_revision: str | None = "0008_media_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("style_id", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_job_id", sa.String(length=160), nullable=True),
        sa.Column("output_storage_key", sa.String(length=512), nullable=True),
        sa.Column("output_mime_type", sa.String(length=100), nullable=True),
        sa.Column("output_width", sa.Integer(), nullable=True),
        sa.Column("output_height", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["city_memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("output_storage_key"),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_image_job_user_request"),
    )
    op.create_index(op.f("ix_image_generation_jobs_memory_id"), "image_generation_jobs", ["memory_id"])
    op.create_index(op.f("ix_image_generation_jobs_source_asset_id"), "image_generation_jobs", ["source_asset_id"])
    op.create_index(op.f("ix_image_generation_jobs_status"), "image_generation_jobs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_image_generation_jobs_status"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_source_asset_id"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_memory_id"), table_name="image_generation_jobs")
    op.drop_table("image_generation_jobs")
