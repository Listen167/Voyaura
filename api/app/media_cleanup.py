from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.errors import AppError
from app.integrations.media_storage import MediaStorage, get_media_storage
from app.models import MediaAsset

SessionFactory = Callable[[], Session]


@dataclass
class CleanupFailure:
    asset_id: str
    code: str
    message: str


@dataclass
class CleanupSummary:
    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    failures: list[CleanupFailure] = field(default_factory=list)


def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def cleanup_expired_media_uploads(
    *,
    storage: MediaStorage | None = None,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
    limit: int | None = None,
) -> CleanupSummary:
    media_storage = storage or get_media_storage()
    cutoff = now or datetime.now(UTC)
    batch_size = limit or settings.media_cleanup_batch_size
    with session_factory() as db:
        asset_ids = list(
            db.scalars(
                select(MediaAsset.id)
                .where(
                    MediaAsset.upload_status == "pending",
                    MediaAsset.upload_expires_at.is_not(None),
                    MediaAsset.upload_expires_at <= cutoff,
                )
                .order_by(MediaAsset.upload_expires_at)
                .limit(batch_size)
            )
        )

    summary = CleanupSummary(scanned=len(asset_ids))
    for asset_id in asset_ids:
        with session_factory() as db:
            try:
                asset = db.scalar(
                    select(MediaAsset)
                    .where(MediaAsset.id == asset_id)
                    .with_for_update(skip_locked=True)
                )
                if (
                    asset is None
                    or asset.upload_status != "pending"
                    or asset.upload_expires_at is None
                    or aware_utc(asset.upload_expires_at) > cutoff
                ):
                    summary.skipped += 1
                    continue
                if asset.thumbnail_key:
                    media_storage.remove(asset.thumbnail_key)
                media_storage.remove(asset.storage_key)
                db.delete(asset)
                db.commit()
                summary.deleted += 1
            except AppError as exc:
                db.rollback()
                summary.failures.append(
                    CleanupFailure(
                        asset_id=str(asset_id),
                        code=exc.code,
                        message=exc.message,
                    )
                )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete expired Voyaura media uploads")
    parser.add_argument(
        "--limit",
        type=int,
        default=settings.media_cleanup_batch_size,
        help="Maximum number of expired uploads to inspect",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit <= 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "MEDIA_CLEANUP_LIMIT_INVALID",
                        "message": "--limit must be greater than zero.",
                    },
                },
                indent=2,
            )
        )
        return 2
    summary = cleanup_expired_media_uploads(limit=args.limit)
    output = {"ok": not summary.failures, **asdict(summary)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
