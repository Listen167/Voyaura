from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app.config import settings
from app.errors import AppError
from app.integrations.media_processing import create_photo_thumbnail, create_video_cover
from app.integrations.media_queue import MediaJobQueue
from app.integrations.media_scanner import get_media_scanner
from app.integrations.media_storage import get_media_storage


def create_test_video(path: Path) -> None:
    result = subprocess.run(
        [
            settings.ffmpeg_path,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0xd65d45:s=320x240:d=1",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise AppError(
            "MEDIA_SMOKE_VIDEO_CREATE_FAILED",
            "FFmpeg could not create the temporary diagnostic video.",
            status_code=500,
            details={"exit_code": result.returncode},
        )


def run_smoke_test() -> dict[str, object]:
    run_id = uuid.uuid4().hex
    queue_key = f"{settings.media_queue_key}:smoke:{run_id}"
    queue = MediaJobQueue(settings.redis_url, queue_key)
    storage = get_media_storage()
    uploaded_keys: list[str] = []
    try:
        storage.ensure_bucket()
        with TemporaryDirectory(prefix="voyaura-smoke-") as temporary_directory:
            root = Path(temporary_directory)
            photo_path = root / "photo.jpg"
            photo_thumbnail_path = root / "photo-thumbnail.webp"
            video_path = root / "video.mp4"
            video_cover_path = root / "video-cover.webp"

            Image.new("RGB", (640, 480), "#d65d45").save(photo_path, format="JPEG")
            create_test_video(video_path)

            scanner = get_media_scanner()
            photo_scan = scanner.scan(str(photo_path))
            video_scan = scanner.scan(str(video_path))
            if photo_scan.infected or video_scan.infected:
                raise AppError(
                    "MEDIA_SMOKE_SCAN_DETECTED",
                    "A generated diagnostic file was unexpectedly detected as malware.",
                    status_code=500,
                )

            photo = create_photo_thumbnail(str(photo_path), str(photo_thumbnail_path))
            video = create_video_cover(
                str(video_path),
                str(video_cover_path),
                ffmpeg_path=settings.ffmpeg_path,
                ffprobe_path=settings.ffprobe_path,
            )

            queue.enqueue(run_id)
            dequeued = queue.dequeue(timeout_seconds=2)
            if dequeued != run_id:
                raise AppError(
                    "MEDIA_SMOKE_QUEUE_MISMATCH",
                    "Redis returned an unexpected diagnostic queue item.",
                    status_code=500,
                )

            files = {
                f"_smoke/{run_id}/photo.jpg": (photo_path, "image/jpeg"),
                f"_smoke/{run_id}/photo-thumbnail.webp": (
                    photo_thumbnail_path,
                    "image/webp",
                ),
                f"_smoke/{run_id}/video.mp4": (video_path, "video/mp4"),
                f"_smoke/{run_id}/video-cover.webp": (video_cover_path, "image/webp"),
            }
            for storage_key, (source_path, content_type) in files.items():
                storage.upload_file(storage_key, str(source_path), content_type=content_type)
                uploaded_keys.append(storage_key)
                stored = storage.stat(storage_key)
                if stored.size <= 0 or stored.content_type != content_type:
                    raise AppError(
                        "MEDIA_SMOKE_STORAGE_MISMATCH",
                        "MinIO returned unexpected diagnostic object metadata.",
                        status_code=500,
                        details={"storage_key": storage_key},
                    )

            signed_get_created = bool(
                storage.presigned_get(uploaded_keys[1], expires=timedelta(minutes=1))
            )
            return {
                "ok": True,
                "scanner": {
                    "provider": settings.media_scanner_provider,
                    "photo": "clean",
                    "video": "clean",
                },
                "redis": {"queue_round_trip": True},
                "photo": {"thumbnail": [photo.width, photo.height], "format": "webp"},
                "video": {
                    "source": [video.width, video.height],
                    "duration_seconds": round(video.duration_seconds, 3),
                    "cover": [video.thumbnail_width, video.thumbnail_height],
                    "format": "webp",
                },
                "minio": {
                    "object_round_trip": True,
                    "signed_get_created": signed_get_created,
                    "cleanup": "completed",
                },
            }
    finally:
        queue.client.delete(queue_key)
        for storage_key in reversed(uploaded_keys):
            storage.remove(storage_key)


def main() -> int:
    try:
        result = run_smoke_test()
    except AppError as exc:
        result = {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "retryable": exc.retryable,
            },
        }
    except Exception as exc:  # noqa: BLE001 - CLI boundary emits a stable diagnostic result
        result = {
            "ok": False,
            "error": {
                "code": "MEDIA_SMOKE_UNEXPECTED_ERROR",
                "message": type(exc).__name__,
                "retryable": False,
            },
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
