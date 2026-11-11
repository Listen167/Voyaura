"""Add secure media upload lifecycle fields.

Revision ID: 0006_media_uploads
Revises: 0005_memory_mutations
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_media_uploads"
down_revision: str | None = "0005_memory_mutations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("client_request_id", sa.Uuid(), nullable=True))
    op.add_column(
        "media_assets",
        sa.Column("visibility", sa.String(length=20), server_default="private", nullable=False),
    )
    op.add_column(
        "media_assets",
        sa.Column("upload_status", sa.String(length=20), server_default="ready", nullable=False),
    )
    op.add_column(
        "media_assets",
        sa.Column(
            "exif_status",
            sa.String(length=24),
            server_default="not_applicable",
            nullable=False,
        ),
    )
    op.add_column("media_assets", sa.Column("failure_code", sa.String(length=64)))
    op.add_column(
        "media_assets",
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "media_assets",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_media_asset_client_request",
        "media_assets",
        ["client_request_id"],
    )
    op.alter_column("media_assets", "visibility", server_default=None)
    op.alter_column("media_assets", "upload_status", server_default=None)
    op.alter_column("media_assets", "exif_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_media_asset_client_request", "media_assets", type_="unique")
    op.drop_column("media_assets", "uploaded_at")
    op.drop_column("media_assets", "upload_expires_at")
    op.drop_column("media_assets", "failure_code")
    op.drop_column("media_assets", "exif_status")
    op.drop_column("media_assets", "upload_status")
    op.drop_column("media_assets", "visibility")
    op.drop_column("media_assets", "client_request_id")
