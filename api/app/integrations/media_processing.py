from __future__ import annotations

import io
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
