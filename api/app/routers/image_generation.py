from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.image_styles import (
    IMAGE_STYLE_MAP,
    IMAGE_STYLES,
    ImageStyle,
    effective_negative_prompt,
    effective_prompt,
    recipe_snapshot,
)
from app.integrations.image_provider import ImageProviderInfo, get_image_provider_info
from app.integrations.image_queue import ImageJobQueue, get_image_queue
from app.integrations.media_storage import MediaStorage, get_media_storage
from app.models import (
    City,
    CityMemory,
    ImageGenerationJob,
    ImageJobMutation,
    MediaAsset,
    User,
)
from app.schemas import (
    ImageCaptionOut,
    ImageCompanionOut,
    ImageJobCreateDraft,
    ImageJobCreateOut,
    ImageJobDeleteConfirmOut,
    ImageJobDeleteDraft,
    ImageJobDeletePreviewOut,
    ImageJobDraft,
    ImageJobFavoriteDraft,
    ImageJobListOut,
    ImageJobOut,
    ImageJobPreviewOut,
    ImageStyleCatalogOut,
    ImageStyleOut,
    ImageStyleRecipeOut,
    ImageStyleSourceOut,
    XiaoxiPhotoCapabilityOut,
)
from app.xiaoxi_photo import companion_snapshot, get_xiaoxi_photo_capability

router = APIRouter(tags=["image-generation"])

RETRYABLE_IMAGE_ERRORS = {"IMAGE_QUEUE_UNAVAILABLE", "COMFYUI_UNAVAILABLE", "COMFYUI_TIMEOUT"}


def caption_snapshot(
    city: City,
    memory: CityMemory,
    mode: str,
    *,
    layout: str,
    palette: str,
    font_style: str,
) -> dict[str, str] | None:
    if mode != "travel_stamp":
        return None
    return {
        "title": memory.title,
        "location": city.name_zh,
        "date": memory.occurred_at.date().isoformat(),
        "layout": layout,
        "palette": palette,
        "font_style": font_style,
    }


def style_out(style: ImageStyle) -> ImageStyleOut:
    return ImageStyleOut(
        id=style.id,
        name=style.name,
        description=style.description,
        swatch=style.swatch,
        recipe=ImageStyleRecipeOut.model_validate(asdict(style.recipe)),
        source=(
            ImageStyleSourceOut.model_validate(asdict(style.source)) if style.source else None
        ),
    )


def require_style(style_id: str) -> ImageStyle:
    style = IMAGE_STYLE_MAP.get(style_id)
    if style is None:
        raise AppError(
            "IMAGE_STYLE_NOT_FOUND",
            "找不到选择的图片风格。",
            status_code=404,
            details={"style_id": style_id},
        )
    return style


def require_source(
    db: Session,
    *,
    username: str,
    asset_id: uuid.UUID,
) -> tuple[User, City, CityMemory, MediaAsset]:
    row = db.execute(
        select(User, City, CityMemory, MediaAsset)
        .join(CityMemory, CityMemory.user_id == User.id)
        .join(City, City.id == CityMemory.city_id)
        .join(MediaAsset, MediaAsset.memory_id == CityMemory.id)
        .where(User.username == username, MediaAsset.id == asset_id)
    ).one_or_none()
    if row is None:
        raise AppError(
            "IMAGE_SOURCE_NOT_FOUND",
            "找不到可用于风格创作的照片。",
            status_code=404,
            details={"source_asset_id": str(asset_id)},
        )
    user, city, memory, asset = row
    if asset.kind != "photo" or asset.upload_status != "ready":
        raise AppError(
            "IMAGE_SOURCE_NOT_READY",
            "只有完成安全处理的照片可以进入风格创作。",
            status_code=409,
            details={"kind": asset.kind, "upload_status": asset.upload_status},
        )
    return user, city, memory, asset


def job_out(
    job: ImageGenerationJob,
    *,
    city: City,
    memory: CityMemory,
    source: MediaAsset,
    storage: MediaStorage | None = None,
) -> ImageJobOut:
    signed_ttl = timedelta(minutes=15)
    style = require_style(job.style_id)
    stored_recipe = job.recipe_snapshot or recipe_snapshot(
        style,
        job.preservation_level,  # type: ignore[arg-type]
    )
    metadata = job.provider_metadata if isinstance(job.provider_metadata, dict) else {}
    model_names = metadata.get("model_names")
    caption = (
        ImageCaptionOut.model_validate(job.caption_snapshot)
        if job.caption_snapshot
        else None
    )
    companion = (
        ImageCompanionOut.model_validate(job.companion_snapshot)
        if job.companion_snapshot
        else None
    )
    return ImageJobOut(
        id=job.id,
        status=job.status,
        source_asset_id=job.source_asset_id,
        source_filename=source.original_filename,
        source_url=(storage.presigned_get(source.storage_key, signed_ttl) if storage else None),
        source_thumbnail_url=(
            storage.presigned_get(source.thumbnail_key, signed_ttl)
            if storage is not None and source.thumbnail_key
            else None
        ),
        city_adcode=city.adcode,
        city_name=city.name_zh,
        memory_id=memory.id,
        memory_title=memory.title,
        style_id=job.style_id,
        provider=job.provider,
        provider_job_id=job.provider_job_id,
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        preservation_level=job.preservation_level,
        recipe=ImageStyleRecipeOut.model_validate(stored_recipe),
        style_source=(
            ImageStyleSourceOut.model_validate(asdict(style.source)) if style.source else None
        ),
        model_names=(
            [str(name) for name in model_names if str(name).strip()]
            if isinstance(model_names, list)
            else []
        ),
        caption_mode=job.caption_mode,
        caption=caption,
        companion=companion,
        is_favorite=job.is_favorite,
        output_url=(
            storage.presigned_get(job.output_storage_key, signed_ttl)
            if storage is not None and job.status == "succeeded" and job.output_storage_key
            else None
        ),
        download_url=(
            storage.presigned_download(
                job.output_storage_key,
                signed_ttl,
                filename=f"voyaura-{city.adcode}-{job.style_id}-{job.id}.webp",
            )
            if storage is not None and job.status == "succeeded" and job.output_storage_key
            else None
        ),
        output_mime_type=job.output_mime_type,
        output_width=job.output_width,
        output_height=job.output_height,
        failure_code=job.failure_code,
        failure_message=job.failure_message,
        retryable=job.failure_code in RETRYABLE_IMAGE_ERRORS,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def require_job_context(
    db: Session,
    *,
    username: str,
    job_id: uuid.UUID,
) -> tuple[User, City, CityMemory, MediaAsset, ImageGenerationJob]:
    row = db.execute(
        select(User, City, CityMemory, MediaAsset, ImageGenerationJob)
        .join(ImageGenerationJob, ImageGenerationJob.user_id == User.id)
        .join(City, City.id == ImageGenerationJob.city_id)
        .join(CityMemory, CityMemory.id == ImageGenerationJob.memory_id)
        .join(MediaAsset, MediaAsset.id == ImageGenerationJob.source_asset_id)
        .where(User.username == username, ImageGenerationJob.id == job_id)
    ).one_or_none()
    if row is None:
        raise AppError("IMAGE_JOB_NOT_FOUND", "找不到图片生成任务。", status_code=404)
    return row


@router.get("/image-styles", response_model=ImageStyleCatalogOut)
def list_image_styles(
    provider_info: Annotated[ImageProviderInfo, Depends(get_image_provider_info)],
) -> ImageStyleCatalogOut:
    companion = get_xiaoxi_photo_capability()
    return ImageStyleCatalogOut(
        provider=provider_info.provider,
        available=provider_info.available,
        missing_settings=list(provider_info.missing_settings),
        styles=[style_out(style) for style in IMAGE_STYLES],
        companion=XiaoxiPhotoCapabilityOut.model_validate(asdict(companion)),
    )


@router.post("/image-jobs/preview", response_model=ImageJobPreviewOut)
def preview_image_job(
    payload: ImageJobDraft,
    db: Annotated[Session, Depends(get_db)],
    provider_info: Annotated[ImageProviderInfo, Depends(get_image_provider_info)],
) -> ImageJobPreviewOut:
    _, city, memory, asset = require_source(
        db,
        username=payload.username,
        asset_id=payload.source_asset_id,
    )
    style = require_style(payload.style_id)
    recipe = recipe_snapshot(style, payload.preservation_level)
    caption = caption_snapshot(
        city,
        memory,
        payload.caption_mode,
        layout=payload.caption_layout,
        palette=payload.caption_palette,
        font_style=payload.caption_font_style,
    )
    companion_capability = get_xiaoxi_photo_capability()
    companion = companion_snapshot(
        enabled=payload.companion_enabled,
        position=payload.companion_position,
        scale=payload.companion_scale,
        require_available=False,
    )
    return ImageJobPreviewOut(
        source_asset_id=asset.id,
        source_filename=asset.original_filename,
        city_adcode=city.adcode,
        city_name=city.name_zh,
        memory_id=memory.id,
        memory_title=memory.title,
        style=style_out(style),
        recipe=ImageStyleRecipeOut.model_validate(recipe),
        effective_prompt=effective_prompt(style, payload.prompt, payload.preservation_level),
        negative_prompt=effective_negative_prompt(style, payload.negative_prompt),
        preservation_level=payload.preservation_level,
        caption_mode=payload.caption_mode,
        caption=ImageCaptionOut.model_validate(caption) if caption else None,
        companion=ImageCompanionOut.model_validate(companion) if companion else None,
        companion_available=companion_capability.available,
        companion_missing_settings=list(companion_capability.missing_settings),
        provider=provider_info.provider,
        provider_available=provider_info.available,
    )


@router.post("/image-jobs", response_model=ImageJobCreateOut)
def create_image_job(
    payload: ImageJobCreateDraft,
    db: Annotated[Session, Depends(get_db)],
    queue: Annotated[ImageJobQueue, Depends(get_image_queue)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    provider_info: Annotated[ImageProviderInfo, Depends(get_image_provider_info)],
) -> ImageJobCreateOut:
    if not provider_info.available:
        raise AppError(
            "IMAGE_PROVIDER_NOT_CONFIGURED",
            "图片生成 Provider 尚未配置完成。",
            status_code=503,
            details={
                "provider": provider_info.provider,
                "missing_settings": list(provider_info.missing_settings),
            },
        )
    user, city, memory, asset = require_source(
        db,
        username=payload.username,
        asset_id=payload.source_asset_id,
    )
    style = require_style(payload.style_id)
    prompt = effective_prompt(style, payload.prompt, payload.preservation_level)
    negative_prompt = effective_negative_prompt(style, payload.negative_prompt)
    caption = caption_snapshot(
        city,
        memory,
        payload.caption_mode,
        layout=payload.caption_layout,
        palette=payload.caption_palette,
        font_style=payload.caption_font_style,
    )
    companion = companion_snapshot(
        enabled=payload.companion_enabled,
        position=payload.companion_position,
        scale=payload.companion_scale,
    )
    existing = db.scalar(
        select(ImageGenerationJob).where(
            ImageGenerationJob.user_id == user.id,
            ImageGenerationJob.client_request_id == payload.client_request_id,
        )
    )
    if existing is not None:
        if (
            existing.source_asset_id != asset.id
            or existing.style_id != style.id
            or existing.prompt != prompt
            or existing.negative_prompt != negative_prompt
            or existing.preservation_level != payload.preservation_level
            or existing.caption_mode != payload.caption_mode
            or existing.caption_snapshot != caption
            or existing.companion_snapshot != companion
        ):
            raise AppError(
                "IMAGE_JOB_IDEMPOTENCY_CONFLICT",
                "该请求编号已经用于另一项图片生成任务。",
                status_code=409,
                details={"client_request_id": str(payload.client_request_id)},
            )
        if existing.status == "queued":
            queue.enqueue(str(existing.id))
        return ImageJobCreateOut(
            status="existing",
            job=job_out(existing, city=city, memory=memory, source=asset, storage=storage),
        )

    job = ImageGenerationJob(
        user_id=user.id,
        city_id=city.id,
        memory_id=memory.id,
        source_asset_id=asset.id,
        client_request_id=payload.client_request_id,
        provider=provider_info.provider,
        style_id=style.id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        preservation_level=payload.preservation_level,
        recipe_snapshot=recipe_snapshot(style, payload.preservation_level),
        caption_mode=payload.caption_mode,
        caption_snapshot=caption,
        companion_snapshot=companion,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    queue.enqueue(str(job.id))
    return ImageJobCreateOut(
        status="created",
        job=job_out(job, city=city, memory=memory, source=asset, storage=storage),
    )


@router.get("/image-jobs", response_model=ImageJobListOut)
def list_image_jobs(
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
    favorite_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ImageJobListOut:
    statement = (
        select(ImageGenerationJob, City, CityMemory, MediaAsset)
        .join(User, User.id == ImageGenerationJob.user_id)
        .join(City, City.id == ImageGenerationJob.city_id)
        .join(CityMemory, CityMemory.id == ImageGenerationJob.memory_id)
        .join(MediaAsset, MediaAsset.id == ImageGenerationJob.source_asset_id)
        .where(User.username == username)
    )
    if favorite_only:
        statement = statement.where(ImageGenerationJob.is_favorite.is_(True))
    statement = statement.order_by(ImageGenerationJob.created_at.desc()).limit(limit)
    rows = db.execute(statement).all()
    return ImageJobListOut(
        items=[
            job_out(job, city=city, memory=memory, source=source, storage=storage)
            for job, city, memory, source in rows
        ]
    )


@router.get("/image-jobs/{job_id}", response_model=ImageJobOut)
def get_image_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
) -> ImageJobOut:
    _, city, memory, source, job = require_job_context(
        db,
        username=username,
        job_id=job_id,
    )
    return job_out(job, city=city, memory=memory, source=source, storage=storage)


@router.post("/image-jobs/{job_id}/favorite", response_model=ImageJobOut)
def set_image_job_favorite(
    job_id: uuid.UUID,
    payload: ImageJobFavoriteDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ImageJobOut:
    _, city, memory, source, job = require_job_context(
        db,
        username=payload.username,
        job_id=job_id,
    )
    job.is_favorite = payload.favorite
    db.commit()
    return job_out(job, city=city, memory=memory, source=source, storage=storage)


@router.post("/image-jobs/{job_id}/delete-preview", response_model=ImageJobDeletePreviewOut)
def preview_image_job_delete(
    job_id: uuid.UUID,
    payload: ImageJobDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
) -> ImageJobDeletePreviewOut:
    _, city, memory, source, job = require_job_context(
        db,
        username=payload.username,
        job_id=job_id,
    )
    if job.status == "running":
        raise AppError(
            "IMAGE_JOB_DELETE_RUNNING_CONFLICT",
            "图片正在生成，请任务完成后再删除。",
            status_code=409,
            retryable=True,
        )
    return ImageJobDeletePreviewOut(
        job_id=job.id,
        source_filename=source.original_filename,
        city_name=city.name_zh,
        memory_title=memory.title,
        style=style_out(require_style(job.style_id)),
        status=job.status,
        has_output=bool(job.output_storage_key),
    )


@router.post("/image-jobs/{job_id}/delete-confirm", response_model=ImageJobDeleteConfirmOut)
def confirm_image_job_delete(
    job_id: uuid.UUID,
    payload: ImageJobDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ImageJobDeleteConfirmOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None:
        raise AppError("USER_NOT_FOUND", "找不到图片任务所属的用户。", status_code=404)
    mutation = db.scalar(
        select(ImageJobMutation).where(
            ImageJobMutation.user_id == user.id,
            ImageJobMutation.client_request_id == payload.client_request_id,
        )
    )
    if mutation is not None:
        if mutation.target_job_id != job_id or mutation.operation != "delete":
            raise AppError(
                "IMAGE_JOB_MUTATION_IDEMPOTENCY_CONFLICT",
                "该请求编号已经用于另一项图片任务操作。",
                status_code=409,
            )
        return ImageJobDeleteConfirmOut(status="existing", job_id=job_id)

    _, _, _, _, job = require_job_context(db, username=payload.username, job_id=job_id)
    if job.status == "running":
        raise AppError(
            "IMAGE_JOB_DELETE_RUNNING_CONFLICT",
            "图片正在生成，请任务完成后再删除。",
            status_code=409,
            retryable=True,
        )
    response = ImageJobDeleteConfirmOut(status="deleted", job_id=job.id)
    if job.output_storage_key:
        storage.remove(job.output_storage_key)
    db.add(
        ImageJobMutation(
            user_id=user.id,
            target_job_id=job.id,
            client_request_id=payload.client_request_id,
            operation="delete",
            response_snapshot=response.model_dump(mode="json"),
        )
    )
    db.delete(job)
    db.commit()
    return response
