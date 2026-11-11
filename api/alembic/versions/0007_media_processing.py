"""Add queued media processing state.

Revision ID: 0007_media_processing
Revises: 0006_media_uploads
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_media_processing"
down_revision: str | None = "0006_media_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("scan_status", sa.String(length=20), server_default="not_scanned", nullable=False),
    )
    op.add_column("media_assets", sa.Column("processing_error", sa.String(length=500)))
    op.add_column("media_assets", sa.Column("thumbnail_mime_type", sa.String(length=100)))
    op.add_column("media_assets", sa.Column("thumbnail_width", sa.Integer()))
    op.add_column("media_assets", sa.Column("thumbnail_height", sa.Integer()))
    op.add_column("media_assets", sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.alter_column("media_assets", "scan_status", server_default=None)


def downgrade() -> None:
    op.drop_column("media_assets", "processed_at")
    op.drop_column("media_assets", "thumbnail_height")
    op.drop_column("media_assets", "thumbnail_width")
    op.drop_column("media_assets", "thumbnail_mime_type")
    op.drop_column("media_assets", "processing_error")
    op.drop_column("media_assets", "scan_status")
