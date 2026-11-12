from __future__ import annotations

import io
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.errors import AppError
from app.integrations.image_provider import ImageProvider, get_image_provider
from app.integrations.media_storage import MediaStorage, get_media_storage
from app.models import ImageGenerationJob, MediaAsset
from app.xiaoxi_photo import compose_xiaoxi_photo

SessionFactory = Callable[[], Session]
logger = logging.getLogger("voyaura.image-jobs")

CAPTION_FONT_CANDIDATES = {
    "sans": (
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ),
    "serif": (
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simkai.ttf",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
        "/System/Library/Fonts/Songti.ttc",
    ),
}

CAPTION_PALETTES = {
    "coral": {
        "paper": (248, 245, 236, 242),
        "accent": (229, 77, 52, 255),
        "title": (38, 45, 40, 255),
        "meta": (88, 98, 91, 255),
    },
    "forest": {
        "paper": (238, 244, 238, 242),
        "accent": (63, 105, 81, 255),
        "title": (30, 49, 38, 255),
        "meta": (72, 92, 79, 255),
    },
    "ink": {
        "paper": (241, 239, 234, 242),
        "accent": (39, 43, 40, 255),
        "title": (28, 31, 29, 255),
        "meta": (83, 85, 81, 255),
    },
}

CAPTION_LAYOUTS = {"archive_band", "postcard_corner", "vertical_stamp"}


def normalize_generated_image(data: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=90, method=4)
            return output.getvalue(), image.width, image.height
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AppError(
            "IMAGE_PROVIDER_OUTPUT_INVALID",
            "图片 Provider 返回了无法识别的输出。",
            status_code=502,
        ) from exc


def resolve_caption_font(configured_path: str = "", style: str = "sans") -> str:
    if configured_path:
        path = Path(configured_path)
        if path.is_file():
            return str(path)
        raise AppError(
            "IMAGE_CAPTION_FONT_UNAVAILABLE",
            "配置的图片标题字体文件不存在。",
            status_code=500,
            details={"font_file": path.name},
        )
    candidates = CAPTION_FONT_CANDIDATES.get(style)
    if candidates is None:
        raise AppError(
            "IMAGE_CAPTION_STYLE_INVALID",
            "旅行印记使用了不支持的字体组合。",
            status_code=422,
            details={"font_style": style},
        )
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    if style != "sans":
        return resolve_caption_font(configured_path, "sans")
    raise AppError(
        "IMAGE_CAPTION_FONT_UNAVAILABLE",
        "系统中找不到可用于中文旅行标题的字体。",
        status_code=500,
        details={"setting": "VOYAURA_IMAGE_CAPTION_FONT_PATH"},
    )


def fitted_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font_path: str,
    target_size: int,
    max_width: int,
) -> ImageFont.FreeTypeFont:
    size = max(10, target_size)
    while size > 10:
        font = ImageFont.truetype(font_path, size=size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(font_path, size=10)


def render_travel_stamp(
    data: bytes,
    caption: dict[str, object],
    *,
    font_path: str = "",
) -> tuple[bytes, int, int]:
    title = str(caption.get("title") or "").strip()
    location = str(caption.get("location") or "").strip()
    date = str(caption.get("date") or "").strip()
    layout = str(caption.get("layout") or "archive_band")
    palette_name = str(caption.get("palette") or "coral")
    font_style = str(caption.get("font_style") or "sans")
    if not title or not location or not date:
        raise AppError(
            "IMAGE_CAPTION_INVALID",
            "旅行标题缺少标题、地点或日期。",
            status_code=422,
        )
    if layout not in CAPTION_LAYOUTS or palette_name not in CAPTION_PALETTES:
        raise AppError(
            "IMAGE_CAPTION_STYLE_INVALID",
            "旅行印记使用了不支持的版式或颜色。",
            status_code=422,
            details={"layout": layout, "palette": palette_name},
        )
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGBA")
            width, height = image.size
            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            padding = max(22, int(width * 0.045))
            colors = CAPTION_PALETTES[palette_name]
            selected_font = resolve_caption_font(font_path, font_style)
            meta_text = f"{location}  ·  {date}"

            if layout == "archive_band":
                band_height = max(72, int(height * 0.17))
                band_top = max(0, height - band_height)
                accent_width = max(6, int(width * 0.008))
                draw.rectangle((0, band_top, width, height), fill=colors["paper"])
                draw.rectangle(
                    (0, band_top, accent_width, height),
                    fill=colors["accent"],
                )
                title_font = fitted_font(
                    draw,
                    title,
                    font_path=selected_font,
                    target_size=max(18, int(height * 0.034)),
                    max_width=width - padding * 2,
                )
                meta_font = fitted_font(
                    draw,
                    meta_text,
                    font_path=selected_font,
                    target_size=max(11, int(height * 0.017)),
                    max_width=width - padding * 2,
                )
                title_y = band_top + max(13, int(band_height * 0.17))
                draw.text(
                    (padding, title_y),
                    title,
                    font=title_font,
                    fill=colors["title"],
                )
                meta_y = title_y + max(title_font.size + 8, int(band_height * 0.48))
                draw.text(
                    (padding, min(meta_y, height - meta_font.size - 8)),
                    meta_text,
                    font=meta_font,
                    fill=colors["meta"],
                )
            elif layout == "postcard_corner":
                margin = max(18, int(min(width, height) * 0.035))
                card_width = min(width - margin * 2, max(220, int(width * 0.58)))
                card_height = min(height - margin * 2, max(96, int(height * 0.2)))
                left = width - margin - card_width
                top = height - margin - card_height
                radius = max(8, int(min(width, height) * 0.012))
                draw.rounded_rectangle(
                    (left, top, width - margin, height - margin),
                    radius=radius,
                    fill=colors["paper"],
                    outline=colors["accent"],
                    width=max(2, int(width * 0.003)),
                )
                inner = max(14, int(card_width * 0.06))
                title_font = fitted_font(
                    draw,
                    title,
                    font_path=selected_font,
                    target_size=max(18, int(height * 0.032)),
                    max_width=card_width - inner * 2,
                )
                meta_font = fitted_font(
                    draw,
                    meta_text,
                    font_path=selected_font,
                    target_size=max(10, int(height * 0.015)),
                    max_width=card_width - inner * 2,
                )
                draw.rectangle(
                    (left + inner, top + inner, left + inner + max(24, card_width // 7), top + inner + 4),
                    fill=colors["accent"],
                )
                draw.text(
                    (left + inner, top + inner + 12),
                    title,
                    font=title_font,
                    fill=colors["title"],
                )
                draw.text(
                    (left + inner, height - margin - inner - meta_font.size),
                    meta_text,
                    font=meta_font,
                    fill=colors["meta"],
                )
            else:
                margin = max(18, int(min(width, height) * 0.035))
                panel_width = min(width - margin * 2, max(112, int(width * 0.2)))
                left = width - margin - panel_width
                draw.rounded_rectangle(
                    (left, margin, width - margin, height - margin),
                    radius=max(8, int(panel_width * 0.08)),
                    fill=colors["paper"],
                )
                draw.rectangle(
                    (width - margin - max(5, int(panel_width * 0.055)), margin, width - margin, height - margin),
                    fill=colors["accent"],
                )
                vertical_title = "\n".join(title.replace(" ", ""))
                title_font = ImageFont.truetype(
                    selected_font,
                    size=max(16, int(min(width, height) * 0.033)),
                )
                max_title_height = height - margin * 2 - max(90, int(height * 0.18))
                while title_font.size > 10:
                    bounds = draw.multiline_textbbox(
                        (0, 0), vertical_title, font=title_font, spacing=4, align="center"
                    )
                    if bounds[3] - bounds[1] <= max_title_height:
                        break
                    title_font = ImageFont.truetype(selected_font, size=title_font.size - 2)
                title_bounds = draw.multiline_textbbox(
                    (0, 0), vertical_title, font=title_font, spacing=4, align="center"
                )
                title_width = title_bounds[2] - title_bounds[0]
                title_x = left + max(10, (panel_width - title_width) // 2)
                title_y = margin + max(16, int(height * 0.035))
                draw.multiline_text(
                    (title_x, title_y),
                    vertical_title,
                    font=title_font,
                    fill=colors["title"],
                    spacing=4,
                    align="center",
                )
                meta_font = fitted_font(
                    draw,
                    location,
                    font_path=selected_font,
                    target_size=max(10, int(height * 0.014)),
                    max_width=panel_width - 24,
                )
                date_font = fitted_font(
                    draw,
                    date,
                    font_path=selected_font,
                    target_size=max(9, int(height * 0.012)),
                    max_width=panel_width - 24,
                )
                meta_y = height - margin - max(66, int(height * 0.1))
                draw.text(
                    (left + 12, meta_y),
                    location,
                    font=meta_font,
                    fill=colors["meta"],
                )
                draw.text(
                    (left + 12, meta_y + meta_font.size + 8),
                    date,
                    font=date_font,
                    fill=colors["meta"],
                )
            composed = Image.alpha_composite(image, overlay).convert("RGB")
            output = io.BytesIO()
            composed.save(output, format="WEBP", quality=90, method=4)
            return output.getvalue(), width, height
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, TypeError) as exc:
        raise AppError(
            "IMAGE_CAPTION_RENDER_FAILED",
            "无法把旅行标题写入生成图片。",
            status_code=500,
        ) from exc


def process_image_job(
    job_id: str | uuid.UUID,
    *,
    storage: MediaStorage | None = None,
    provider: ImageProvider | None = None,
    session_factory: SessionFactory = SessionLocal,
) -> str:
    media_storage = storage or get_media_storage()
    with session_factory() as db:
        job = db.get(ImageGenerationJob, uuid.UUID(str(job_id)))
        if job is None:
            return "missing"
        if job.status == "succeeded":
            return "succeeded"
        if job.status not in {"queued", "failed"}:
            return job.status
        source = db.get(MediaAsset, job.source_asset_id)
        if source is None or source.kind != "photo" or source.upload_status != "ready":
            job.status = "failed"
            job.failure_code = "IMAGE_SOURCE_NOT_READY"
            job.failure_message = "源照片不存在或尚未完成处理。"
            job.completed_at = datetime.now(UTC)
            db.commit()
            return "failed"

        job.status = "running"
        job.failure_code = None
        job.failure_message = None
        job.updated_at = datetime.now(UTC)
        db.commit()
        try:
            image_provider = provider or get_image_provider()
            with TemporaryDirectory(prefix="voyaura-image-") as temporary_directory:
                suffix = Path(source.storage_key).suffix or ".img"
                source_path = str(Path(temporary_directory) / f"source{suffix}")
                media_storage.download_to_file(
                    source.storage_key,
                    source_path,
                    max_bytes=settings.media_photo_max_bytes,
                )
                generated = image_provider.generate(
                    source_path,
                    prompt=job.prompt,
                    negative_prompt=job.negative_prompt,
                )
            normalized, width, height = normalize_generated_image(generated.data)
            if job.companion_snapshot:
                normalized, width, height = compose_xiaoxi_photo(
                    normalized,
                    job.companion_snapshot,
                    asset_path=settings.xiaoxi_photo_asset_path,
                )
            if job.caption_mode == "travel_stamp" and job.caption_snapshot:
                normalized, width, height = render_travel_stamp(
                    normalized,
                    job.caption_snapshot,
                    font_path=settings.image_caption_font_path,
                )
            output_key = f"{job.user_id}/generated/{job.id}/output.webp"
            media_storage.replace(output_key, normalized, content_type="image/webp")
            job.status = "succeeded"
            job.provider_job_id = generated.provider_job_id
            job.output_storage_key = output_key
            job.output_mime_type = "image/webp"
            job.output_width = width
            job.output_height = height
            job.provider_metadata = generated.metadata
            job.updated_at = datetime.now(UTC)
            job.completed_at = job.updated_at
            db.commit()
            return "succeeded"
        except AppError as exc:
            job.status = "failed"
            job.failure_code = exc.code
            job.failure_message = exc.message[:500]
            job.updated_at = datetime.now(UTC)
            job.completed_at = job.updated_at
            db.commit()
            return "failed"
        except Exception:
            logger.exception("image_generation_error job_id=%s", job.id)
            db.rollback()
            job.status = "failed"
            job.failure_code = "IMAGE_GENERATION_ERROR"
            job.failure_message = "图片生成发生未识别错误。"
            job.updated_at = datetime.now(UTC)
            job.completed_at = job.updated_at
            db.commit()
            return "failed"
