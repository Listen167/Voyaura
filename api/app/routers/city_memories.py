import hashlib
import json
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.errors import AppError
from app.integrations.media_storage import MediaStorage, get_media_storage
from app.models import City, CityMemory, CityVisit, MemoryMutation, User, utcnow
from app.schemas import (
    CityMemoryConfirmOut,
    CityMemoryDeleteConfirmOut,
    CityMemoryDeleteDraft,
    CityMemoryDeletePreviewOut,
    CityMemoryDetailOut,
    CityMemoryDraft,
    CityMemoryItemOut,
    CityMemoryPreviewOut,
    CityMemoryStatsOut,
    CityMemoryUpdateConfirmOut,
    CityMemoryUpdatePreviewOut,
    MediaAssetOut,
    VisitedCityOut,
)

router = APIRouter(prefix="/cities", tags=["city-memories"])


def require_visited_city(
    db: Session,
    *,
    username: str,
    adcode: str,
) -> tuple[User, City, CityVisit]:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise AppError("USER_NOT_FOUND", "找不到城市记忆所属的用户。", status_code=404)

    city = db.scalar(select(City).where(City.adcode == adcode))
    if city is None:
        raise AppError(
            "CITY_NOT_FOUND",
            "找不到对应的城市。",
            status_code=404,
            details={"adcode": adcode},
        )

    visit = db.scalar(
        select(CityVisit).where(CityVisit.user_id == user.id, CityVisit.city_id == city.id)
    )
    if visit is None:
        raise AppError(
            "CITY_NOT_VISITED",
            "这座城市尚未被当前用户点亮。",
            status_code=404,
            details={"adcode": adcode, "username": username},
        )
    return user, city, visit


def memory_out(memory: CityMemory, storage: MediaStorage | None = None) -> CityMemoryItemOut:
    return CityMemoryItemOut(
        id=memory.id,
        title=memory.title,
        body=memory.body,
        occurred_at=memory.occurred_at,
        visibility=memory.visibility,
        media=[
            MediaAssetOut(
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
                    storage.presigned_get(
                        asset.thumbnail_key,
                        timedelta(minutes=15),
                    )
                    if storage is not None and asset.thumbnail_key
                    else None
                ),
                content_url=(
                    storage.presigned_get(asset.storage_key, timedelta(minutes=15))
                    if storage is not None
                    else None
                ),
                thumbnail_width=asset.thumbnail_width,
                thumbnail_height=asset.thumbnail_height,
                created_at=asset.created_at,
            )
            for asset in memory.media_assets
            if asset.upload_status == "ready"
        ],
    )


def normalized_title(title: str) -> str:
    value = title.strip()
    if not value:
        raise AppError(
            "MEMORY_TITLE_EMPTY",
            "记忆标题不能只包含空格。",
            status_code=422,
        )
    return value


def normalized_body(body: str | None) -> str | None:
    value = body.strip() if body else ""
    return value or None


def require_memory(
    db: Session,
    *,
    user: User,
    city: City,
    memory_id: uuid.UUID,
) -> CityMemory:
    memory = db.scalar(
        select(CityMemory)
        .options(selectinload(CityMemory.media_assets))
        .where(
            CityMemory.id == memory_id,
            CityMemory.user_id == user.id,
            CityMemory.city_id == city.id,
        )
    )
    if memory is None:
        raise AppError(
            "MEMORY_NOT_FOUND",
            "找不到当前城市中要操作的记忆。",
            status_code=404,
            details={"memory_id": str(memory_id), "adcode": city.adcode},
        )
    return memory


def mutation_hash(
    operation: str,
    memory_id: uuid.UUID,
    payload: CityMemoryDraft | None = None,
) -> str:
    content: dict[str, object] = {
        "operation": operation,
        "memory_id": str(memory_id),
    }
    if payload is not None:
        content.update(
            {
                "title": normalized_title(payload.title),
                "body": normalized_body(payload.body),
                "occurred_at": payload.occurred_at.isoformat(),
                "visibility": payload.visibility,
            }
        )
    serialized = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def matching_mutation(
    db: Session,
    *,
    user: User,
    city: City,
    memory_id: uuid.UUID,
    client_request_id: uuid.UUID,
    operation: str,
    payload_hash: str,
) -> MemoryMutation | None:
    mutation = db.scalar(
        select(MemoryMutation).where(
            MemoryMutation.user_id == user.id,
            MemoryMutation.client_request_id == client_request_id,
        )
    )
    if mutation is None:
        return None
    if (
        mutation.city_id != city.id
        or mutation.target_memory_id != memory_id
        or mutation.operation != operation
        or mutation.payload_hash != payload_hash
    ):
        raise AppError(
            "MEMORY_MUTATION_IDEMPOTENCY_CONFLICT",
            "该请求编号已经用于另一项记忆变更。",
            status_code=409,
            details={"client_request_id": str(client_request_id)},
        )
    return mutation


@router.get("/{adcode}/memories", response_model=CityMemoryDetailOut)
def get_city_memories(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
) -> CityMemoryDetailOut:
    user, city, visit = require_visited_city(db, username=username, adcode=adcode)

    memories = db.scalars(
        select(CityMemory)
        .options(selectinload(CityMemory.media_assets))
        .where(CityMemory.user_id == user.id, CityMemory.city_id == city.id)
        .order_by(CityMemory.occurred_at.desc())
    ).all()

    items = [memory_out(memory, storage) for memory in memories]
    photo_count = sum(asset.kind == "photo" for memory in items for asset in memory.media)
    vlog_assets = [asset for memory in items for asset in memory.media if asset.kind == "vlog"]
    vlog_minutes = round(sum(asset.duration_seconds or 0 for asset in vlog_assets) / 60)

    return CityMemoryDetailOut(
        city=VisitedCityOut(
            adcode=city.adcode,
            name_zh=city.name_zh,
            name_en=city.name_en,
            province_zh=city.province_zh,
            longitude=city.longitude,
            latitude=city.latitude,
            first_visited_at=visit.first_visited_at,
            last_visited_at=visit.last_visited_at,
            memory_count=len(items),
            check_in_source=visit.check_in_source,
        ),
        visit_note=visit.note,
        stats=CityMemoryStatsOut(
            memories=len(items),
            photos=photo_count,
            vlogs=len(vlog_assets),
            vlog_minutes=vlog_minutes,
        ),
        memories=items,
    )


@router.post("/{adcode}/memories/preview", response_model=CityMemoryPreviewOut)
def preview_city_memory(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    payload: CityMemoryDraft,
    db: Annotated[Session, Depends(get_db)],
) -> CityMemoryPreviewOut:
    _, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    return CityMemoryPreviewOut(
        city_adcode=city.adcode,
        city_name=city.name_zh,
        title=normalized_title(payload.title),
        body=normalized_body(payload.body),
        occurred_at=payload.occurred_at,
        visibility=payload.visibility,
    )


@router.post("/{adcode}/memories/confirm", response_model=CityMemoryConfirmOut)
def confirm_city_memory(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    payload: CityMemoryDraft,
    db: Annotated[Session, Depends(get_db)],
) -> CityMemoryConfirmOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    existing = db.scalar(
        select(CityMemory)
        .options(selectinload(CityMemory.media_assets))
        .where(
            CityMemory.user_id == user.id,
            CityMemory.client_request_id == payload.client_request_id,
        )
    )
    if existing is not None:
        if existing.city_id != city.id:
            raise AppError(
                "MEMORY_IDEMPOTENCY_CONFLICT",
                "该请求编号已经用于另一座城市的记忆。",
                status_code=409,
                details={"client_request_id": str(payload.client_request_id)},
            )
        return CityMemoryConfirmOut(status="existing", memory=memory_out(existing))

    memory = CityMemory(
        user_id=user.id,
        city_id=city.id,
        client_request_id=payload.client_request_id,
        title=normalized_title(payload.title),
        body=normalized_body(payload.body),
        occurred_at=payload.occurred_at,
        visibility=payload.visibility,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return CityMemoryConfirmOut(status="created", memory=memory_out(memory))


@router.post(
    "/{adcode}/memories/{memory_id}/update-preview",
    response_model=CityMemoryUpdatePreviewOut,
)
def preview_memory_update(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: CityMemoryDraft,
    db: Annotated[Session, Depends(get_db)],
) -> CityMemoryUpdatePreviewOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    require_memory(db, user=user, city=city, memory_id=memory_id)
    return CityMemoryUpdatePreviewOut(
        memory_id=memory_id,
        city_adcode=city.adcode,
        city_name=city.name_zh,
        title=normalized_title(payload.title),
        body=normalized_body(payload.body),
        occurred_at=payload.occurred_at,
        visibility=payload.visibility,
    )


@router.post(
    "/{adcode}/memories/{memory_id}/update-confirm",
    response_model=CityMemoryUpdateConfirmOut,
)
def confirm_memory_update(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: CityMemoryDraft,
    db: Annotated[Session, Depends(get_db)],
) -> CityMemoryUpdateConfirmOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    payload_hash = mutation_hash("update", memory_id, payload)
    mutation = matching_mutation(
        db,
        user=user,
        city=city,
        memory_id=memory_id,
        client_request_id=payload.client_request_id,
        operation="update",
        payload_hash=payload_hash,
    )
    if mutation is not None:
        return CityMemoryUpdateConfirmOut(
            status="existing",
            memory=CityMemoryItemOut.model_validate(mutation.response_snapshot["memory"]),
        )

    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    memory.title = normalized_title(payload.title)
    memory.body = normalized_body(payload.body)
    memory.occurred_at = payload.occurred_at
    memory.visibility = payload.visibility
    memory.updated_at = utcnow()
    response = CityMemoryUpdateConfirmOut(status="updated", memory=memory_out(memory))
    db.add(
        MemoryMutation(
            user_id=user.id,
            city_id=city.id,
            target_memory_id=memory.id,
            client_request_id=payload.client_request_id,
            operation="update",
            payload_hash=payload_hash,
            response_snapshot=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response


@router.post(
    "/{adcode}/memories/{memory_id}/delete-preview",
    response_model=CityMemoryDeletePreviewOut,
)
def preview_memory_delete(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: CityMemoryDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
) -> CityMemoryDeletePreviewOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    return CityMemoryDeletePreviewOut(
        memory_id=memory.id,
        city_adcode=city.adcode,
        city_name=city.name_zh,
        title=memory.title,
        occurred_at=memory.occurred_at,
        media_count=len(memory.media_assets),
    )


@router.post(
    "/{adcode}/memories/{memory_id}/delete-confirm",
    response_model=CityMemoryDeleteConfirmOut,
)
def confirm_memory_delete(
    adcode: Annotated[str, Path(min_length=6, max_length=12)],
    memory_id: uuid.UUID,
    payload: CityMemoryDeleteDraft,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> CityMemoryDeleteConfirmOut:
    user, city, _ = require_visited_city(db, username=payload.username, adcode=adcode)
    payload_hash = mutation_hash("delete", memory_id)
    mutation = matching_mutation(
        db,
        user=user,
        city=city,
        memory_id=memory_id,
        client_request_id=payload.client_request_id,
        operation="delete",
        payload_hash=payload_hash,
    )
    if mutation is not None:
        return CityMemoryDeleteConfirmOut(
            status="existing",
            memory_id=memory_id,
            city_adcode=city.adcode,
        )

    memory = require_memory(db, user=user, city=city, memory_id=memory_id)
    response = CityMemoryDeleteConfirmOut(
        status="deleted",
        memory_id=memory.id,
        city_adcode=city.adcode,
    )
    db.add(
        MemoryMutation(
            user_id=user.id,
            city_id=city.id,
            target_memory_id=memory.id,
            client_request_id=payload.client_request_id,
            operation="delete",
            payload_hash=payload_hash,
            response_snapshot=response.model_dump(mode="json"),
        )
    )
    for asset in memory.media_assets:
        if asset.thumbnail_key:
            storage.remove(asset.thumbnail_key)
        storage.remove(asset.storage_key)
    db.delete(memory)
    db.commit()
    return response
