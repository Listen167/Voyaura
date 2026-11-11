from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.integrations.amap import AMapClient, ResolvedCity, get_amap_client
from app.models import City, CityVisit, User
from app.schemas import (
    CheckInConfirmOut,
    CheckInCoordinates,
    CheckInPreviewOut,
    ManualCityCheckIn,
    VisitedCityOut,
)

router = APIRouter(prefix="/check-ins", tags=["check-ins"])


def require_user(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise AppError("USER_NOT_FOUND", "找不到要点亮城市的用户。", status_code=404)
    return user


def resolve_city(client: AMapClient, payload: CheckInCoordinates) -> ResolvedCity:
    return client.resolve_wgs84_city(payload.longitude, payload.latitude)


def preview_resolved_city(
    db: Session,
    user: User,
    resolved: ResolvedCity,
    *,
    accuracy_meters: float | None,
    location_source: str,
) -> CheckInPreviewOut:
    already_lit = db.scalar(
        select(CityVisit)
        .join(City)
        .where(CityVisit.user_id == user.id, City.adcode == resolved.adcode)
    )
    return CheckInPreviewOut(
        adcode=resolved.adcode,
        city_name=resolved.name_zh,
        province_name=resolved.province_zh,
        city_center=(resolved.longitude, resolved.latitude),
        map_position=(resolved.gcj_longitude, resolved.gcj_latitude),
        formatted_address=resolved.formatted_address,
        accuracy_meters=accuracy_meters,
        already_lit=already_lit is not None,
        location_source=location_source,
    )


def upsert_visit(
    db: Session,
    user: User,
    resolved: ResolvedCity,
    *,
    source: str,
) -> CheckInConfirmOut:
    city = db.scalar(select(City).where(City.adcode == resolved.adcode))
    if city is None:
        city = City(
            adcode=resolved.adcode,
            name_zh=resolved.name_zh,
            name_en=resolved.name_zh,
            province_zh=resolved.province_zh,
            longitude=resolved.longitude,
            latitude=resolved.latitude,
        )
        db.add(city)
        db.flush()
    else:
        city.name_zh = resolved.name_zh
        city.province_zh = resolved.province_zh
        city.longitude = resolved.longitude
        city.latitude = resolved.latitude

    visit = db.scalar(
        select(CityVisit).where(CityVisit.user_id == user.id, CityVisit.city_id == city.id)
    )
    now = datetime.now(UTC)
    if visit is None:
        visit = CityVisit(
            user_id=user.id,
            city_id=city.id,
            first_visited_at=now,
            last_visited_at=now,
            check_in_source=source,
        )
        db.add(visit)
        status = "created"
    else:
        visit.last_visited_at = now
        visit.check_in_source = source
        status = "updated"

    db.commit()
    db.refresh(visit)
    return CheckInConfirmOut(
        status=status,
        city=VisitedCityOut(
            adcode=city.adcode,
            name_zh=city.name_zh,
            name_en=city.name_en,
            province_zh=city.province_zh,
            longitude=city.longitude,
            latitude=city.latitude,
            first_visited_at=visit.first_visited_at,
            last_visited_at=visit.last_visited_at,
            check_in_source=visit.check_in_source,
        ),
    )


def manual_resolved_city(payload: ManualCityCheckIn) -> ResolvedCity:
    formatted_address = payload.city_name
    if payload.province_name != payload.city_name:
        formatted_address = f"{payload.province_name}{payload.city_name}"
    return ResolvedCity(
        adcode=payload.adcode,
        name_zh=payload.city_name,
        province_zh=payload.province_name,
        longitude=payload.longitude,
        latitude=payload.latitude,
        formatted_address=formatted_address,
        gcj_longitude=payload.longitude,
        gcj_latitude=payload.latitude,
    )


@router.post("/preview", response_model=CheckInPreviewOut)
def preview_check_in(
    payload: CheckInCoordinates,
    db: Annotated[Session, Depends(get_db)],
    amap: Annotated[AMapClient, Depends(get_amap_client)],
) -> CheckInPreviewOut:
    user = require_user(db, payload.username)
    resolved = resolve_city(amap, payload)
    return preview_resolved_city(
        db,
        user,
        resolved,
        accuracy_meters=payload.accuracy_meters,
        location_source="device",
    )


@router.post("/confirm", response_model=CheckInConfirmOut)
def confirm_check_in(
    payload: CheckInCoordinates,
    db: Annotated[Session, Depends(get_db)],
    amap: Annotated[AMapClient, Depends(get_amap_client)],
) -> CheckInConfirmOut:
    user = require_user(db, payload.username)
    resolved = resolve_city(amap, payload)

    return upsert_visit(db, user, resolved, source="device")


@router.post("/manual-preview", response_model=CheckInPreviewOut)
def preview_manual_check_in(
    payload: ManualCityCheckIn,
    db: Annotated[Session, Depends(get_db)],
) -> CheckInPreviewOut:
    user = require_user(db, payload.username)
    return preview_resolved_city(
        db,
        user,
        manual_resolved_city(payload),
        accuracy_meters=None,
        location_source=payload.source,
    )


@router.post("/manual-confirm", response_model=CheckInConfirmOut)
def confirm_manual_check_in(
    payload: ManualCityCheckIn,
    db: Annotated[Session, Depends(get_db)],
) -> CheckInConfirmOut:
    user = require_user(db, payload.username)
    return upsert_visit(db, user, manual_resolved_city(payload), source=payload.source)
