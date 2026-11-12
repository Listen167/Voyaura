from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

PreservationLevel = Literal["balanced", "high"]


@dataclass(frozen=True)
class ImageStyleSource:
    name: str
    version: str
    url: str
    license: str


@dataclass(frozen=True)
class ImageStyleRecipe:
    version: str
    aspect_ratio: str
    layout: str
    focal_element: str
    typography: str
    color: str
    texture: str
    default_preservation: PreservationLevel = "balanced"


@dataclass(frozen=True)
class ImageStyle:
    id: str
    name: str
    description: str
    swatch: str
    prompt_suffix: str
    negative_suffix: str
    recipe: ImageStyleRecipe
    source: ImageStyleSource | None = None


IMAGE_STYLES = (
    ImageStyle(
        id="retro_film",
        name="复古胶片",
        description="温和颗粒、自然肤色与旅行底片质感",
        swatch="#b94f3d",
        prompt_suffix=(
            "retro travel film photography, fine grain, natural skin tone, muted highlights"
        ),
        negative_suffix="plastic skin, crushed shadows, oversaturated colors",
        recipe=ImageStyleRecipe(
            version="voyaura-1",
            aspect_ratio="source",
            layout="full-frame photograph",
            focal_element="recognizable source subject",
            typography="none",
            color="warm film palette",
            texture="fine analog grain",
        ),
    ),
    ImageStyle(
        id="minimal_zine_poster",
        name="诗性纸感 Zine",
        description="大面积留白、单一高彩色与微编辑旅行海报",
        swatch="#e6572f",
        prompt_suffix=(
            "tall 3:5 paper poster, warm fibrous scanned paper, 75 percent open paper, "
            "one small off-axis travel-photo cluster, concrete photo crop as the focal element, "
            "sparse archive microtext, one tomato-red printed accent, xerox softness and "
            "risograph grain, flat orthographic scan, quiet diary-like editorial mood"
        ),
        negative_suffix=(
            "full-bleed scene, commercial headline, product ad, logo, CTA, glossy mockup, "
            "hard shadow, 3D render, neon, dense scrapbook, multicolor palette, long text block"
        ),
        recipe=ImageStyleRecipe(
            version="minimal-zine-v0.3.1",
            aspect_ratio="3:5",
            layout="off-axis micro editorial cluster with 70-90% negative space",
            focal_element="recognizable travel-photo crop or printed fragment",
            typography="short archive note and date-like microtext",
            color="one high-chroma accent carried by printed ink",
            texture="paper fibers, xerox softness, risograph grain, slight misregistration",
            default_preservation="high",
        ),
        source=ImageStyleSource(
            name="GC Minimal Zine Poster",
            version="0.3.1",
            url="https://github.com/LiamGvchi/gc-minimal-zine-poster",
            license="MIT",
        ),
    ),
    ImageStyle(
        id="editorial_zine",
        name="旅行杂志",
        description="克制排版感、纸张纹理与编辑视觉",
        swatch="#d3a42f",
        prompt_suffix="independent travel zine editorial, paper texture, bold clean composition",
        negative_suffix="commercial advertising, crowded layout, glossy magazine mockup",
        recipe=ImageStyleRecipe(
            version="voyaura-1",
            aspect_ratio="source",
            layout="editorial photo spread",
            focal_element="large travel photograph",
            typography="minimal editorial caption",
            color="one warm editorial accent",
            texture="subtle uncoated paper",
        ),
    ),
    ImageStyle(
        id="watercolor_postcard",
        name="水彩明信片",
        description="保留场景轮廓的轻盈手绘质感",
        swatch="#4f8175",
        prompt_suffix=(
            "delicate watercolor travel postcard, recognizable architecture, soft pigment texture"
        ),
        negative_suffix="unrecognizable architecture, heavy paint, muddy colors",
        recipe=ImageStyleRecipe(
            version="voyaura-1",
            aspect_ratio="source",
            layout="postcard scene",
            focal_element="recognizable architecture or landscape",
            typography="none",
            color="light natural pigment",
            texture="watercolor paper and soft pigment edge",
            default_preservation="high",
        ),
    ),
    ImageStyle(
        id="night_neon",
        name="城市夜霓虹",
        description="适合夜景的霓虹反射与电影色彩",
        swatch="#315f78",
        prompt_suffix=(
            "cinematic city night, realistic neon reflections, deep contrast, detailed atmosphere"
        ),
        negative_suffix="daylight, flat lighting, fantasy skyline, illegible signs",
        recipe=ImageStyleRecipe(
            version="voyaura-1",
            aspect_ratio="source",
            layout="cinematic city frame",
            focal_element="recognizable night city subject",
            typography="none",
            color="controlled cyan and coral reflections",
            texture="cinematic fine grain",
        ),
    ),
)

IMAGE_STYLE_MAP = {style.id: style for style in IMAGE_STYLES}


def recipe_snapshot(style: ImageStyle, preservation_level: PreservationLevel) -> dict[str, str]:
    snapshot = asdict(style.recipe)
    snapshot["preservation_level"] = preservation_level
    return snapshot


def effective_prompt(
    style: ImageStyle,
    prompt: str,
    preservation_level: PreservationLevel,
) -> str:
    preservation = "high" if preservation_level == "high" else "medium"
    source_contract = (
        f"Use the supplied photograph as the edit target with {preservation} preservation. "
        "Keep the main subject, people identity and clothing when present, architecture, and "
        "travel context recognizable."
    )
    detail = prompt.strip()
    parts = [source_contract]
    if detail:
        parts.append(detail)
    parts.append(style.prompt_suffix)
    return " ".join(parts)


def effective_negative_prompt(style: ImageStyle, prompt: str | None) -> str:
    detail = (prompt or "").strip()
    return f"{detail}, {style.negative_suffix}" if detail else style.negative_suffix
