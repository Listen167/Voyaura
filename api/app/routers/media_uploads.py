from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi import Path as ApiPath
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import AppError
from app.integrations.media_processing import sanitize_image, validate_video_prefix
from app.integrations.media_queue import MediaJobQueue, get_media_queue
from app.integrations.media_storage import MediaStorage, get_media_storage
from app.models import CityMemory, MediaAsset, MediaMutation
from app.routers.city_memories import require_memory, require_visited_city
from app.schemas import (
    MediaAssetOut,
    MediaDeleteConfirmOut,
    MediaDeleteDraft,
    MediaDeletePreviewOut,
    MediaProcessingStatusOut,
    MediaTaskListOut,
    MediaTaskOut,
    MediaUploadCompleteDraft,
    MediaUploadCompleteOut,
    MediaUploadDraft,
    MediaUploadIntentOut,
    MediaUploadPreviewOut,
)

router = APIRouter(prefix="/cities", tags=["media-uploads"])

RETRYABLE_PROCESSING_ERRORS = {
    "MEDIA_QUEUE_UNAVAILABLE",
    "MEDIA_SCANNER_UNAVAILABLE",
    "MEDIA_STORAGE_UNAVAILABLE",
    "MEDIA_PROCESSING_ERROR",
}

MEDIA_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "photo": {
        "image/jpeg": (".jpg", ".jpeg"),
        "image/png": (".png",),
        "image/webp": (".webp",),
    },
    "vlog": {
        "video/mp4": (".mp4",),
        "video/quicktime": (".mov",),
        "video/webm": (".webm",),
    },
}


def clean_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = "".join(character for character in basename if character >= " " and character != "\x7f")
    if not cleaned or len(cleaned) > 255:
        raise AppError(
            "MEDIA_FILENAME_INVALID",
            "文件名为空、过长或包含无效字符。",
            status_code=422,
        )
    return cleaned


def normalize_mime_type(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def max_bytes_for(kind: Literal["photo", "vlog"]) -> int:
    return settings.media_photo_max_bytes if kind == "photo" else settings.media_vlog_max_bytes


def validate_metadata(payload: MediaUploadDraft) -> tuple[str, str, str]:
    filename = clean_filename(payload.filename)
    mime_type = normalize_mime_type(payload.mime_type)
    allowed_extensions = MEDIA_RULES[payload.kind].get(mime_type)
    if allowed_extensions is None:
        raise AppError(
            "MEDIA_TYPE_UNSUPPORTED",
            "仅支持 JPEG、PNG、WebP 图片和 MP4、MOV、WebM 视频。",
            status_code=422,
            details={"kind": payload.kind, "mime_type": mime_type},
        )
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        raise AppError(
            "MEDIA_FILENAME_MISMATCH",
            "文件扩展名与声明的媒体类型不一致。",
            status_code=422,
            details={"extension": extension, "mime_type": mime_type},
        )
    max_bytes = max_bytes_for(payload.kind)
    if payload.byte_size > max_bytes:
        raise AppError(
            "MEDIA_FILE_TOO_LARGE",
            "上传文件超过允许大小。",
            status_code=413,
            details={"kind": payload.kind, "max_bytes": max_bytes},
        )
    return filename, mime_type, extension


def reserved_bytes(db: Session, user_id: uuid.UUID) -> int:
    now = datetime.now(UTC)
    total = db.scalar(
        select(func.coalesce(func.sum(MediaAsset.byte_size), 0))
        .join(CityMemory, MediaAsset.memory_id == CityMemory.id)
        .where(
            CityMemory.user_id == user_id,
            or_(
                MediaAsset.upload_status == "ready",
                MediaAsset.upload_status == "processing",
                and_(
                    MediaAsset.upload_status == "pending",
                    or_(
                        MediaAsset.upload_expires_at.is_(None),
                        MediaAsset.upload_expires_at > now,
                    ),
                ),
            ),
        )
    )
    return int(total or 0)


def check_quota(db: Session, *, user_id: uuid.UUID, requested_bytes: int) -> int:
    used_bytes = reserved_bytes(db, user_id)
    if used_bytes + requested_bytes > settings.media_user_quota_bytes:
        raise AppError(
            "MEDIA_QUOTA_EXCEEDED",
            "媒体存储配额不足，请删除不需要的文件后重试。",
            status_code=413,
            details={
                "quota_bytes": settings.media_user_quota_bytes,
                "used_bytes": used_bytes,
                "requested_bytes": requested_bytes,
            },
        )
    return settings.media_user_quota_bytes - used_bytes - requested_bytes


def media_out(asset: MediaAsset, storage: MediaStorage | None = None) -> MediaAssetOut:
    expires = timedelta(minutes=settings.media_upload_ttl_minutes)
    return MediaAssetOut(
        id=asset.id,
        kind=asset.kind,
        original_filename=asset.original_filename,
        mime_type=asset.mime_type,
        width=asset.width,
        height=asset.height,
        duration_seconds=asset.duration_seconds,
        visibility=asset.visibility,
        upload_status="ready",
        exif_status=asset.exif_status,
        scan_status=asset.scan_status,
        thumbnail_url=(
            storage.presigned_get(asset.thumbnail_key, expires)
            if storage is not None and asset.thumbnail_key
            else None
        ),
        content_url=(
            storage.presigned_get(asset.storage_key, expires) if storage is not None else None
        ),
        thumbnail_width=asset.thumbnail_width,
        thumbnail_height=asset.thumbnail_height,
        created_at=asset.created_at,
    )


def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def intent_expired(asset: MediaAsset) -> bool:
    return asset.upload_expires_at is None or aware_utc(asset.upload_expires_at) <= datetime.now(UTC)


def require_asset(
    db: Session,
    *,
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    lock: bool = False,
) -> MediaAsset:
    statement = select(MediaAsset).where(
        MediaAsset.id == asset_id,
        MediaAsset.memory_id == memory_id,
    )
    if lock:
        statement = statement.with_for_update()
    asset = db.scalar(statement)
    if asset is None:
        raise AppError(
            "MEDIA_ASSET_NOT_FOUND",
            "找不到当前记忆中的媒体上传记录。",
            status_code=404,
            details={"asset_id": str(asset_id), "memory_id": str(memory_id)},
        )
    return asset


def media_delete_hash(memory_id: uuid.UUID, asset_id: uuid.UUID) -> str:
    return hashlib.sha256(f"delete:{memory_id}:{asset_id}".encode()).hexdigest()


def matching_media_mutation(
    db: Session,
    *,
    user_id: uuid.UUID,
    city_id: uuid.UUID,
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    client_request_id: uuid.UUID,
    payload_hash: str,
) -> MediaMutation | None:
    mutation = db.scalar(
        select(MediaMutation).where(
            MediaMutation.user_id == user_id,
            MediaMutation.client_request_id == client_request_id,
        )
    )
    if mutation is None:
        return None
    if (
        mutation.city_id != city_id
        or mutation.target_memory_id != memory_id
        or mutation.target_asset_id != asset_id
        or mutation.operation != "delete"
        or mutation.payload_hash != payload_hash
    ):
        raise AppError(
            "MEDIA_MUTATION_IDEMPOTENCY_CONFLICT",
            "该请求编号已经用于另一项媒体操作。",
            status_code=409,
            details={"client_request_id": str(client_request_id)},
        )
    return mutation


def ensure_asset_deletable(asset: MediaAsset) -> None:
    if asset.upload_status == "processing":
        raise AppError(
            "MEDIA_DELETE_PROCESSING_CONFLICT",
            "媒体仍在安全处理中，请处理完成后再删除。",
            status_code=409,
            details={"asset_id": str(asset.id)},
            retryable=True,
        )


def reject_upload(
    db: Session,
    storage: MediaStorage,
    asset: MediaAsset,
    error: AppError,
) -> None:
    try:
        storage.remove(asset.storage_key)
    except AppError:
        pass
    asset.upload_status = "failed"
    asset.failure_code = error.code
    db.commit()
    raise error


@router.post(
    "/{adcode}/memories/{memory_id}/media/upload-preview",
    response_model=MediaUploadPreviewOut,
)
def preview_media_upload(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: MediaUploadDraft,
    db: Annotated[Session, Depends(get_db)],
) -> MediaUploadPreviewOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    require_memory(db, user=user, city=city, memory_id=memory_id)
    filename, mime_type, _ = validate_metadata(payload)
    remaining = check_quota(db, user_id=user.id, requested_bytes=payload.byte_size)
    return MediaUploadPreviewOut(
        kind=payload.kind,
        filename=filename,
        mime_type=mime_type,
        byte_size=payload.byte_size,
        quota_remaining_bytes=remaining,
    )


@router.post(
    "/{adcode}/memories/{memory_id}/media/upload-intents",
    response_model=MediaUploadIntentOut,
)
def create_media_upload_intent(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: MediaUploadDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> MediaUploadIntentOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    filename, mime_type, extension = validate_metadata(payload)
    existing = db.scalar(
        select(MediaAsset).where(MediaAsset.client_request_id == payload.client_request_id)
    )
    if existing is not None:
        if (
            existing.memory_id != memory.id
            or existing.kind != payload.kind
            or existing.original_filename != filename
            or existing.mime_type != mime_type
            or existing.byte_size != payload.byte_size
        ):
            raise AppError(
                "MEDIA_UPLOAD_IDEMPOTENCY_CONFLICT",
                "该请求编号已经用于另一项媒体上传。",
                status_code=409,
                details={"client_request_id": str(payload.client_request_id)},
            )
        if existing.upload_status == "failed":
            raise AppError(
                "MEDIA_UPLOAD_FAILED_STATE",
                "该上传任务已失败，请重新选择文件并创建新的上传任务。",
                status_code=409,
                details={"failure_code": existing.failure_code},
            )
        if existing.upload_status == "ready":
            raise AppError(
                "MEDIA_UPLOAD_ALREADY_COMPLETE",
                "该文件已经完成上传，无需再次上传。",
                status_code=409,
            )
        if intent_expired(existing):
            raise AppError(
                "MEDIA_UPLOAD_INTENT_EXPIRED",
                "上传地址已经过期，请重新选择文件。",
                status_code=410,
            )
        expires_at = aware_utc(existing.upload_expires_at)  # type: ignore[arg-type]
        expires = timedelta(seconds=max(1, int((expires_at - datetime.now(UTC)).total_seconds())))
        return MediaUploadIntentOut(
            status="existing",
            asset_id=existing.id,
            upload_url=storage.presigned_put(existing.storage_key, expires),
            required_headers={"Content-Type": existing.mime_type},
            expires_at=expires_at,
        )

    check_quota(db, user_id=user.id, requested_bytes=payload.byte_size)
    asset_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.media_upload_ttl_minutes)
    storage_key = f"{user.id}/{city.adcode}/{memory.id}/{asset_id}/original{extension}"
    upload_url = storage.presigned_put(
        storage_key,
        timedelta(minutes=settings.media_upload_ttl_minutes),
    )
    asset = MediaAsset(
        id=asset_id,
        memory_id=memory.id,
        client_request_id=payload.client_request_id,
        kind=payload.kind,
        storage_key=storage_key,
        original_filename=filename,
        mime_type=mime_type,
        byte_size=payload.byte_size,
        visibility="private",
        upload_status="pending",
        exif_status="pending_removal" if payload.kind == "photo" else "not_applicable",
        upload_expires_at=expires_at,
    )
    db.add(asset)
    db.commit()
    return MediaUploadIntentOut(
        status="created",
        asset_id=asset.id,
        upload_url=upload_url,
        required_headers={"Content-Type": mime_type},
        expires_at=expires_at,
    )


@router.post(
    "/{adcode}/memories/{memory_id}/media/{asset_id}/complete",
    response_model=MediaUploadCompleteOut,
)
def complete_media_upload(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    payload: MediaUploadCompleteDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    queue: Annotated[MediaJobQueue, Depends(get_media_queue)],
) -> MediaUploadCompleteOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    require_memory(db, user=user, city=city, memory_id=memory_id)
    asset = require_asset(db, memory_id=memory_id, asset_id=asset_id, lock=True)
    if asset.upload_status == "ready":
        return MediaUploadCompleteOut(
            status="existing",
            asset_id=asset.id,
            asset=media_out(asset, storage),
        )
    if asset.upload_status == "processing":
        queue.enqueue(str(asset.id))
        return MediaUploadCompleteOut(status="processing", asset_id=asset.id)
    if asset.upload_status == "failed":
        if asset.failure_code in RETRYABLE_PROCESSING_ERRORS:
            asset.upload_status = "processing"
            asset.scan_status = "pending"
            asset.failure_code = None
            asset.processing_error = None
            db.commit()
            queue.enqueue(str(asset.id))
            return MediaUploadCompleteOut(status="processing", asset_id=asset.id)
        raise AppError(
            "MEDIA_UPLOAD_FAILED_STATE",
            "该上传任务已失败，请重新选择文件并创建新的上传任务。",
            status_code=409,
            details={"failure_code": asset.failure_code},
        )
    if intent_expired(asset):
        raise AppError(
            "MEDIA_UPLOAD_INTENT_EXPIRED",
            "上传地址已经过期，请重新选择文件。",
            status_code=410,
        )

    stored = storage.stat(asset.storage_key)
    if stored.size != asset.byte_size:
        reject_upload(
            db,
            storage,
            asset,
            AppError(
                "MEDIA_UPLOAD_SIZE_MISMATCH",
                "对象存储中的文件大小与上传确认信息不一致。",
                status_code=422,
                details={"declared_bytes": asset.byte_size, "stored_bytes": stored.size},
            ),
        )
    stored_mime_type = normalize_mime_type(stored.content_type)
    if stored_mime_type != asset.mime_type:
        reject_upload(
            db,
            storage,
            asset,
            AppError(
                "MEDIA_CONTENT_MISMATCH",
                "对象存储中的内容类型与上传确认信息不一致。",
                status_code=422,
                details={"declared_mime_type": asset.mime_type, "stored_mime_type": stored_mime_type},
            ),
        )

    try:
        if asset.kind == "photo":
            raw = storage.read(asset.storage_key, max_bytes=settings.media_photo_max_bytes)
            image = sanitize_image(raw, asset.mime_type)
            storage.replace(asset.storage_key, image.data, content_type=image.mime_type)
            asset.byte_size = len(image.data)
            asset.width = image.width
            asset.height = image.height
            asset.exif_status = "removed"
        else:
            validate_video_prefix(storage.read_prefix(asset.storage_key), asset.mime_type)
    except AppError as exc:
        if exc.code.startswith("MEDIA_IMAGE") or exc.code in {
            "MEDIA_CONTENT_MISMATCH",
            "MEDIA_VIDEO_INVALID",
            "MEDIA_FILE_TOO_LARGE",
        }:
            reject_upload(db, storage, asset, exc)
        raise

    asset.upload_status = "processing"
    asset.scan_status = "pending"
    asset.failure_code = None
    asset.processing_error = None
    asset.uploaded_at = datetime.now(UTC)
    db.commit()
    db.refresh(asset)
    queue.enqueue(str(asset.id))
    return MediaUploadCompleteOut(status="processing", asset_id=asset.id)


@router.get(
    "/{adcode}/memories/{memory_id}/media/{asset_id}/status",
    response_model=MediaProcessingStatusOut,
)
def get_media_processing_status(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
) -> MediaProcessingStatusOut:
    user, city, _ = require_visited_city(db, username=username, adcode=adcode)
    require_memory(db, user=user, city=city, memory_id=memory_id)
    asset = require_asset(db, memory_id=memory_id, asset_id=asset_id)
    status = asset.upload_status
    return MediaProcessingStatusOut(
        status=status,
        asset_id=asset.id,
        scan_status=asset.scan_status,
        failure_code=asset.failure_code,
        failure_message=asset.processing_error,
        retryable=asset.failure_code in RETRYABLE_PROCESSING_ERRORS,
        asset=media_out(asset, storage) if status == "ready" else None,
    )


@router.get("/{adcode}/media/tasks", response_model=MediaTaskListOut)
def list_media_tasks(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
) -> MediaTaskListOut:
    user, city, _ = require_visited_city(db, username=username, adcode=adcode)
    rows = db.execute(
        select(MediaAsset, CityMemory.title)
        .join(CityMemory, MediaAsset.memory_id == CityMemory.id)
        .where(
            CityMemory.user_id == user.id,
            CityMemory.city_id == city.id,
            MediaAsset.upload_status != "ready",
        )
        .order_by(MediaAsset.created_at.desc())
    ).all()
    now = datetime.now(UTC)
    return MediaTaskListOut(
        items=[
            MediaTaskOut(
                asset_id=asset.id,
                memory_id=asset.memory_id,
                memory_title=memory_title,
                kind=asset.kind,
                original_filename=asset.original_filename,
                byte_size=asset.byte_size,
                upload_status=asset.upload_status,
                scan_status=asset.scan_status,
                failure_code=asset.failure_code,
                failure_message=asset.processing_error,
                retryable=asset.failure_code in RETRYABLE_PROCESSING_ERRORS,
                expired=(
                    asset.upload_status == "pending"
                    and asset.upload_expires_at is not None
                    and aware_utc(asset.upload_expires_at) <= now
                ),
                upload_expires_at=asset.upload_expires_at,
                created_at=asset.created_at,
            )
            for asset, memory_title in rows
        ]
    )


@router.post(
    "/{adcode}/memories/{memory_id}/media/{asset_id}/delete-preview",
    response_model=MediaDeletePreviewOut,
)
def preview_media_delete(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    payload: MediaDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
) -> MediaDeletePreviewOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    asset = require_asset(db, memory_id=memory.id, asset_id=asset_id)
    ensure_asset_deletable(asset)
    return MediaDeletePreviewOut(
        asset_id=asset.id,
        memory_id=memory.id,
        city_adcode=city.adcode,
        city_name=city.name_zh,
        memory_title=memory.title,
        kind=asset.kind,
        original_filename=asset.original_filename,
        byte_size=asset.byte_size,
        upload_status=asset.upload_status,
    )


@router.post(
    "/{adcode}/memories/{memory_id}/media/{asset_id}/delete-confirm",
    response_model=MediaDeleteConfirmOut,
)
def confirm_media_delete(
    adcode: Annotated[str, ApiPath(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    asset_id: uuid.UUID,
    payload: MediaDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> MediaDeleteConfirmOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    payload_hash = media_delete_hash(memory_id, asset_id)
    mutation = matching_media_mutation(
        db,
        user_id=user.id,
        city_id=city.id,
        memory_id=memory_id,
        asset_id=asset_id,
        client_request_id=payload.client_request_id,
        payload_hash=payload_hash,
    )
    if mutation is not None:
        return MediaDeleteConfirmOut(
            status="existing",
            asset_id=asset_id,
            memory_id=memory_id,
            city_adcode=city.adcode,
        )

    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    asset = require_asset(db, memory_id=memory.id, asset_id=asset_id, lock=True)
    ensure_asset_deletable(asset)
    response = MediaDeleteConfirmOut(
        status="deleted",
        asset_id=asset.id,
        memory_id=memory.id,
        city_adcode=city.adcode,
    )
    if asset.thumbnail_key:
        storage.remove(asset.thumbnail_key)
    storage.remove(asset.storage_key)
    db.add(
        MediaMutation(
            user_id=user.id,
            city_id=city.id,
            target_memory_id=memory.id,
            target_asset_id=asset.id,
            client_request_id=payload.client_request_id,
            operation="delete",
            payload_hash=payload_hash,
            response_snapshot=response.model_dump(mode="json"),
        )
    )
    db.delete(asset)
    db.commit()
    return response
