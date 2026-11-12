import uuid
from collections import Counter, defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.errors import AppError
from app.models import CityMemory, CityVisit, MediaAsset, User
from app.schemas import (
    MapOverviewOut,
    MapStats,
    MapYearCityActivity,
    MapYearSummary,
    VisitedCityOut,
)

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

    memory_rows = db.execute(
        select(CityMemory.city_id, CityMemory.occurred_at).where(
            CityMemory.user_id == user.id
        )
    ).all()
    memory_counts = Counter(city_id for city_id, _ in memory_rows)
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

    media_rows = db.execute(
        select(MediaAsset.kind, MediaAsset.duration_seconds, CityMemory.occurred_at)
        .join(CityMemory, MediaAsset.memory_id == CityMemory.id)
        .where(
            CityMemory.user_id == user.id,
            MediaAsset.upload_status == "ready",
        )
    ).all()
    memory_total = len(memory_rows)
    photo_total = sum(kind == "photo" for kind, _, _ in media_rows)
    vlog_minutes = round(
        sum(float(duration or 0) for kind, duration, _ in media_rows if kind == "vlog") / 60
    )

    cities_by_id = {visit.city_id: visit.city for visit in visits}
    yearly_city_ids: dict[int, set[uuid.UUID]] = defaultdict(set)
    yearly_memory_counts: dict[int, Counter[uuid.UUID]] = defaultdict(Counter)
    yearly_photo_counts: Counter[int] = Counter()
    yearly_vlog_seconds: defaultdict[int, float] = defaultdict(float)

    for visit in visits:
        yearly_city_ids[visit.first_visited_at.year].add(visit.city_id)
        yearly_city_ids[visit.last_visited_at.year].add(visit.city_id)
    for city_id, occurred_at in memory_rows:
        year = occurred_at.year
        yearly_city_ids[year].add(city_id)
        yearly_memory_counts[year][city_id] += 1
    for kind, duration, occurred_at in media_rows:
        year = occurred_at.year
        if kind == "photo":
            yearly_photo_counts[year] += 1
        elif kind == "vlog":
            yearly_vlog_seconds[year] += float(duration or 0)

    year_summaries = []
    for year in sorted(yearly_city_ids, reverse=True):
        city_ids = yearly_city_ids[year]
        year_summaries.append(
            MapYearSummary(
                year=year,
                stats=MapStats(
                    lit_cities=len(city_ids),
                    memories=sum(yearly_memory_counts[year].values()),
                    photos=yearly_photo_counts[year],
                    vlog_minutes=round(yearly_vlog_seconds[year] / 60),
                ),
                cities=[
                    MapYearCityActivity(
                        adcode=cities_by_id[city_id].adcode,
                        memory_count=yearly_memory_counts[year][city_id],
                    )
                    for city_id in sorted(
                        city_ids,
                        key=lambda item: cities_by_id[item].adcode,
                    )
                ],
            )
        )

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
        year_summaries=year_summaries,
    )

