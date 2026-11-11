from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.errors import AppError
from app.models import CityMemory, CityVisit, MediaAsset, User
from app.schemas import MapOverviewOut, MapStats, VisitedCityOut

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/overview", response_model=MapOverviewOut)
def get_map_overview(
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Query()] = "AuroraRovella",
) -> MapOverviewOut:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise AppError("USER_NOT_FOUND", "找不到地图所属的用户。", status_code=404)

    visits = db.scalars(
        select(CityVisit)
        .options(joinedload(CityVisit.city))
        .where(CityVisit.user_id == user.id)
        .order_by(CityVisit.last_visited_at.desc())
    ).all()

    memory_counts = dict(
        db.execute(
            select(CityMemory.city_id, func.count(CityMemory.id))
            .where(CityMemory.user_id == user.id)
            .group_by(CityMemory.city_id)
        ).all()
    )
    visited_cities = [
        VisitedCityOut(
            adcode=visit.city.adcode,
            name_zh=visit.city.name_zh,
            name_en=visit.city.name_en,
            province_zh=visit.city.province_zh,
            longitude=visit.city.longitude,
            latitude=visit.city.latitude,
            first_visited_at=visit.first_visited_at,
            last_visited_at=visit.last_visited_at,
            memory_count=memory_counts.get(visit.city_id, 0),
            check_in_source=visit.check_in_source,
        )
        for visit in visits
    ]

    media_totals = db.execute(
        select(
            func.count(MediaAsset.id).filter(MediaAsset.kind == "photo"),
            func.coalesce(
                func.sum(MediaAsset.duration_seconds).filter(MediaAsset.kind == "vlog"),
                0,
            ),
        )
        .join(CityMemory, MediaAsset.memory_id == CityMemory.id)
        .where(
            CityMemory.user_id == user.id,
            MediaAsset.upload_status == "ready",
        )
    ).one()
    memory_total = sum(memory_counts.values())
    photo_total = int(media_totals[0] or 0)
    vlog_minutes = round(float(media_totals[1] or 0) / 60)

    return MapOverviewOut(
        username=user.username,
        map_center=(104.1954, 35.8617),
        default_zoom=4.7,
        stats=MapStats(
            lit_cities=len(visited_cities),
            memories=memory_total,
            photos=photo_total,
            vlog_minutes=vlog_minutes,
        ),
        visited_cities=visited_cities,
    )

