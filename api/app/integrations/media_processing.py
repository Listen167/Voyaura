from __future__ import annotations

import io
import json
import math
import subprocess
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import AppError

Image.MAX_IMAGE_PIXELS = 40_000_000

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "JPEG"),
    "PNG": ("image/png", "PNG"),
    "WEBP": ("image/webp", "WEBP"),
}


@dataclass(frozen=True)
class SanitizedImage:
    data: bytes
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class DerivedMedia:
    width: int
    height: int
    duration_seconds: float | None = None


@dataclass(frozen=True)
class VideoDerivatives:
    width: int
    height: int
    duration_seconds: float
    thumbnail_width: int
    thumbnail_height: int


def sanitize_image(data: bytes, expected_mime_type: str) -> SanitizedImage:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if getattr(source, "is_animated", False):
                raise AppError(
                    "MEDIA_IMAGE_ANIMATED_UNSUPPORTED",
                    "暂不支持上传动态图片，请改用静态 JPEG、PNG 或 WebP。",
                    status_code=422,
                )
            detected = IMAGE_FORMATS.get(str(source.format or "").upper())
            if detected is None or detected[0] != expected_mime_type:
                raise AppError(
                    "MEDIA_CONTENT_MISMATCH",
                    "图片实际格式与声明的 MIME 类型不一致。",
                    status_code=422,
                    details={"declared_mime_type": expected_mime_type},
                )
            image = ImageOps.exif_transpose(source)
            image.load()
            mime_type, output_format = detected
            if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            output = io.BytesIO()
            save_options: dict[str, object] = {}
            if output_format == "JPEG":
                save_options = {"quality": 92, "optimize": True}
            elif output_format == "PNG":
                save_options = {"optimize": True}
            elif output_format == "WEBP":
                save_options = {"quality": 90, "method": 4}
            image.save(output, format=output_format, **save_options)
            return SanitizedImage(
                data=output.getvalue(),
                mime_type=mime_type,
                width=image.width,
                height=image.height,
            )
    except AppError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AppError(
            "MEDIA_IMAGE_INVALID",
            "图片文件损坏、尺寸异常或无法识别。",
            status_code=422,
        ) from exc


def validate_video_prefix(data: bytes, expected_mime_type: str) -> None:
    is_iso_video = len(data) >= 12 and data[4:8] == b"ftyp"
    is_webm = data.startswith(b"\x1a\x45\xdf\xa3")
    valid = is_webm if expected_mime_type == "video/webm" else is_iso_video
    if not valid:
        raise AppError(
            "MEDIA_VIDEO_INVALID",
            "视频文件头与声明格式不一致或无法识别。",
            status_code=422,
            details={"declared_mime_type": expected_mime_type},
        )


def create_photo_thumbnail(source_path: str, output_path: str) -> DerivedMedia:
    try:
        with Image.open(source_path) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            image.thumbnail((960, 960), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output_path, format="WEBP", quality=84, method=4)
            return DerivedMedia(width=image.width, height=image.height)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AppError(
            "MEDIA_THUMBNAIL_FAILED",
            "无法为照片生成缩略图。",
            status_code=422,
        ) from exc


def create_video_cover(
    source_path: str,
    output_path: str,
    *,
    ffmpeg_path: str,
    ffprobe_path: str,
) -> VideoDerivatives:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        probe = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                source_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
            creationflags=creation_flags,
        )
        if probe.returncode != 0:
            raise ValueError("ffprobe failed")
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams") or []
        if not streams:
            raise ValueError("video stream missing")
        width = int(streams[0].get("width") or 0)
        height = int(streams[0].get("height") or 0)
        duration = float((metadata.get("format") or {}).get("duration") or 0)
        if width <= 0 or height <= 0 or not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid video metadata")
        seek_seconds = min(3.0, max(0.1, duration * 0.1))
        cover = subprocess.run(
            [
                ffmpeg_path,
                "-v",
                "error",
                "-ss",
                f"{seek_seconds:.3f}",
                "-i",
                source_path,
                "-frames:v",
                "1",
                "-vf",
                (
                    "scale=960:540:force_original_aspect_ratio=decrease,"
                    "pad=960:540:(ow-iw)/2:(oh-ih)/2:color=0x272b28"
                ),
                "-an",
                "-c:v",
                "libwebp",
                "-q:v",
                "75",
                "-y",
                output_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
            creationflags=creation_flags,
        )
        if cover.returncode != 0:
            raise ValueError("ffmpeg cover extraction failed")
        with Image.open(output_path) as generated:
            thumbnail_width, thumbnail_height = generated.size
        return VideoDerivatives(
            width=width,
            height=height,
            duration_seconds=duration,
            thumbnail_width=thumbnail_width,
            thumbnail_height=thumbnail_height,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        raise AppError(
            "MEDIA_VIDEO_PROCESSING_FAILED",
            "无法读取视频信息或生成封面。",
            status_code=422,
        ) from exc
