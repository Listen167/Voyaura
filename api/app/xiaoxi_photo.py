from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError

from app.config import settings
from app.errors import AppError

CompanionPosition = Literal["left", "right"]
CompanionScale = Literal["small", "medium", "large"]


@dataclass(frozen=True)
class XiaoxiPhotoCapability:
    available: bool
    missing_settings: tuple[str, ...]
    asset_version: str | None
    positions: tuple[CompanionPosition, ...] = ("left", "right")
    scales: tuple[CompanionScale, ...] = ("small", "medium", "large")
    poses: tuple[str, ...] = ("default",)
    expressions: tuple[str, ...] = ("warm",)


def get_xiaoxi_photo_capability() -> XiaoxiPhotoCapability:
    asset_path = settings.xiaoxi_photo_asset_path.strip()
    missing: list[str] = []
    if not asset_path:
        missing.append("XIAOXI_PHOTO_ASSET_PATH")
    elif not Path(asset_path).is_file():
        missing.append("XIAOXI_PHOTO_ASSET_FILE")
    if settings.xiaoxi_photo_asset_version.strip() in {"", "unconfigured"}:
        missing.append("XIAOXI_PHOTO_ASSET_VERSION")
    return XiaoxiPhotoCapability(
        available=not missing,
        missing_settings=tuple(missing),
        asset_version=(settings.xiaoxi_photo_asset_version.strip() or None),
    )


def companion_snapshot(
    *,
    enabled: bool,
    position: CompanionPosition,
    scale: CompanionScale,
    require_available: bool = True,
) -> dict[str, object] | None:
    if not enabled:
        return None
    capability = get_xiaoxi_photo_capability()
    if require_available and not capability.available:
        raise AppError(
            "XIAOXI_ASSET_NOT_CONFIGURED",
            "小曦合照素材尚未配置完成。",
            status_code=503,
            details={"missing_settings": list(capability.missing_settings)},
        )
    return {
        "asset_version": capability.asset_version,
        "pose": "default",
        "expression": "warm",
        "position": position,
        "scale": scale,
        "method": "deterministic_alpha_composite",
        "disclosure": "小曦角色使用经授权透明素材进行确定性合成。",
    }


def compose_xiaoxi_photo(
    data: bytes,
    snapshot: dict[str, object],
    *,
    asset_path: str,
) -> tuple[bytes, int, int]:
    position = str(snapshot.get("position") or "")
    scale = str(snapshot.get("scale") or "")
    if position not in {"left", "right"} or scale not in {"small", "medium", "large"}:
        raise AppError(
            "XIAOXI_COMPOSITION_INVALID",
            "小曦合照的站位或尺寸配置无效。",
            status_code=422,
        )
    if not asset_path or not Path(asset_path).is_file():
        raise AppError(
            "XIAOXI_ASSET_NOT_CONFIGURED",
            "图片 worker 找不到小曦透明素材。",
            status_code=500,
            details={"setting": "VOYAURA_XIAOXI_PHOTO_ASSET_PATH"},
        )
    try:
        with Image.open(io.BytesIO(data)) as background_source:
            background = background_source.convert("RGBA")
        with Image.open(asset_path) as character_source:
            character = character_source.convert("RGBA")
            character.load()
        if character.getchannel("A").getextrema() == (255, 255):
            raise AppError(
                "XIAOXI_ASSET_ALPHA_REQUIRED",
                "小曦合照素材必须包含透明通道。",
                status_code=422,
            )

        width, height = background.size
        scale_ratio = {"small": 0.25, "medium": 0.34, "large": 0.43}[scale]
        target_height = max(32, int(height * scale_ratio))
        target_width = max(20, round(character.width * target_height / character.height))
        character = character.resize((target_width, target_height), Image.Resampling.LANCZOS)
        character = ImageEnhance.Brightness(character).enhance(0.98)

        margin_x = max(18, int(width * 0.045))
        margin_bottom = max(16, int(height * 0.035))
        x = margin_x if position == "left" else width - target_width - margin_x
        y = height - target_height - margin_bottom

        alpha = character.getchannel("A")
        shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
        shadow_mask = Image.new("L", background.size, 0)
        shadow_mask.paste(alpha, (x + max(3, width // 300), y + max(5, height // 180)))
        shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(max(3, width // 180))))
        shadow_color = Image.new("RGBA", background.size, (20, 25, 22, 70))
        shadow = Image.composite(shadow_color, shadow, shadow.getchannel("A"))
        composed = Image.alpha_composite(background, shadow)
        composed.alpha_composite(character, (x, y))

        output = io.BytesIO()
        composed.convert("RGB").save(output, format="WEBP", quality=90, method=4)
        return output.getvalue(), width, height
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise AppError(
            "XIAOXI_COMPOSITION_FAILED",
            "无法把小曦角色合成到旅行照片。",
            status_code=500,
        ) from exc
