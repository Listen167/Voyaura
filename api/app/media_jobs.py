from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.errors import AppError
from app.integrations.media_processing import create_photo_thumbnail, create_video_cover
from app.integrations.media_scanner import ScanResult, get_media_scanner
from app.integrations.media_storage import get_media_storage
from app.models import MediaAsset

SessionFactory = Callable[[], Session]
logger = logging.getLogger("voyaura.media-jobs")


class MediaProcessingStorage(Protocol):
    def download_to_file(self, storage_key: str, path: str, *, max_bytes: int) -> None: ...

    def upload_file(self, storage_key: str, path: str, *, content_type: str) -> None: ...

    def remove(self, storage_key: str) -> None: ...


class MediaProcessingScanner(Protocol):
    def scan(self, path: str) -> ScanResult: ...


def process_media_asset(
    asset_id: str | uuid.UUID,
    *,
    storage: MediaProcessingStorage | None = None,
    scanner: MediaProcessingScanner | None = None,
    session_factory: SessionFactory = SessionLocal,
) -> str:
    media_storage = storage or get_media_storage()
    with session_factory() as db:
        asset = db.get(MediaAsset, uuid.UUID(str(asset_id)))
        if asset is None:
            return "missing"
        if asset.upload_status == "ready":
            return "ready"
        if asset.upload_status != "processing":
            return asset.upload_status

        asset.scan_status = "scanning"
        asset.processing_error = None
        db.commit()

        max_bytes = (
            settings.media_photo_max_bytes
            if asset.kind == "photo"
            else settings.media_vlog_max_bytes
        )
        try:
            media_scanner = scanner or get_media_scanner()
            with TemporaryDirectory(prefix="voyaura-media-") as temporary_directory:
                source_suffix = Path(asset.storage_key).suffix or ".bin"
                source_path = str(Path(temporary_directory) / f"original{source_suffix}")
                thumbnail_path = str(Path(temporary_directory) / "thumbnail.webp")
                media_storage.download_to_file(
                    asset.storage_key,
                    source_path,
                    max_bytes=max_bytes,
                )
                scan_result = media_scanner.scan(source_path)
                if scan_result.infected:
                    media_storage.remove(asset.storage_key)
                    asset.upload_status = "failed"
                    asset.scan_status = "infected"
                    asset.failure_code = "MEDIA_MALWARE_DETECTED"
                    asset.processing_error = "媒体文件未通过安全扫描。"
                    db.commit()
                    return "infected"

                asset.scan_status = "clean"
                if asset.kind == "photo":
                    derived = create_photo_thumbnail(source_path, thumbnail_path)
                    asset.thumbnail_width = derived.width
                    asset.thumbnail_height = derived.height
                else:
                    derived_video = create_video_cover(
                        source_path,
                        thumbnail_path,
                        ffmpeg_path=settings.ffmpeg_path,
                        ffprobe_path=settings.ffprobe_path,
                    )
                    asset.width = derived_video.width
                    asset.height = derived_video.height
                    asset.duration_seconds = derived_video.duration_seconds
                    asset.thumbnail_width = derived_video.thumbnail_width
                    asset.thumbnail_height = derived_video.thumbnail_height

                thumbnail_key = f"{asset.storage_key.rsplit('/', 1)[0]}/thumbnail.webp"
                media_storage.upload_file(
                    thumbnail_key,
                    thumbnail_path,
                    content_type="image/webp",
                )
                asset.thumbnail_key = thumbnail_key
                asset.thumbnail_mime_type = "image/webp"
                asset.upload_status = "ready"
                asset.failure_code = None
                asset.processing_error = None
                asset.processed_at = datetime.now(UTC)
                db.commit()
                return "ready"
        except AppError as exc:
            asset.upload_status = "failed"
            if asset.scan_status == "scanning":
                asset.scan_status = "error"
            asset.failure_code = exc.code
            asset.processing_error = exc.message[:500]
            db.commit()
            return "failed"
        # This worker boundary keeps unexpected failures queryable through the status API.
        except Exception:
            logger.exception("media_processing_error asset_id=%s", asset.id)
            db.rollback()
            asset.upload_status = "failed"
            if asset.scan_status == "scanning":
                asset.scan_status = "error"
            asset.failure_code = "MEDIA_PROCESSING_ERROR"
            asset.processing_error = "媒体处理发生未识别错误。"
            db.commit()
            return "failed"
