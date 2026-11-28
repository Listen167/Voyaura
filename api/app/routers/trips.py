import hashlib
import json
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_actor_username
from app.database import get_db
from app.errors import AppError
from app.models import ItineraryStop, Trip, TripDay, User
from app.schemas import (
    TripCreateDraft,
    TripCreateOut,
    TripDayOut,
    TripDetailOut,
    TripListOut,
    TripStatus,
    TripSummaryOut,
)

router = APIRouter(prefix="/trips", tags=["itineraries"])


def _request_fingerprint(payload: TripCreateDraft) -> str:
    content = payload.model_dump(mode="json", exclude={"username", "client_request_id"})
    serialized = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _trip_query():
    return select(Trip).options(
        selectinload(Trip.user),
        selectinload(Trip.days)
        .selectinload(TripDay.stops)
        .selectinload(ItineraryStop.meal_suggestion),
        selectinload(Trip.days).selectinload(TripDay.transfer_legs),
        selectinload(Trip.evidence),
    )


def _summary_out(trip: Trip) -> TripSummaryOut:
    return TripSummaryOut(
        id=trip.id,
        username=trip.user.username,
        title=trip.title,
        status=trip.status,
        origin_city_name=trip.origin_city_name,
        origin_city_adcode=trip.origin_city_adcode,
        destination_city_name=trip.destination_city_name,
        destination_city_adcode=trip.destination_city_adcode,
        start_date=trip.start_date,
        end_date=trip.end_date,
        day_count=trip.day_count,
        timezone=trip.timezone,
        party_type=trip.party_type,
        pace=trip.pace,
        interests=trip.interests,
        transport_modes=trip.transport_modes,
        total_budget_yuan=trip.total_budget_yuan,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


def _detail_out(trip: Trip) -> TripDetailOut:
    summary = _summary_out(trip)
    return TripDetailOut(
        **summary.model_dump(),
        dietary_constraints=trip.dietary_constraints,
        daily_start_time=trip.daily_start_time,
        daily_end_time=trip.daily_end_time,
        requirements_snapshot=trip.requirements_snapshot,
        confirmed_at=trip.confirmed_at,
        days=[TripDayOut.model_validate(day) for day in trip.days],
        evidence=trip.evidence,
    )


def _require_user(db: Session, username: str) -> User:
    require_actor_username(db, username)
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise AppError(
            "USER_NOT_FOUND",
            "找不到行程所属的用户。",
            status_code=404,
            details={"username": username},
        )
    return user


def _require_trip(db: Session, trip_id: uuid.UUID, username: str) -> Trip:
    require_actor_username(db, username)
    trip = db.scalar(
        _trip_query().where(Trip.id == trip_id, Trip.user.has(User.username == username))
    )
    if trip is None:
        raise AppError(
            "TRIP_NOT_FOUND",
            "找不到当前用户的行程。",
            status_code=404,
            details={"trip_id": str(trip_id), "username": username},
        )
    return trip


@router.post("", response_model=TripCreateOut, status_code=201)
def create_trip(
    payload: TripCreateDraft,
    db: Annotated[Session, Depends(get_db)],
) -> TripCreateOut:
    user = _require_user(db, payload.username)
    fingerprint = _request_fingerprint(payload)
    existing = db.scalar(
        _trip_query().where(
            Trip.user_id == user.id,
            Trip.client_request_id == payload.client_request_id,
        )
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise AppError(
                "TRIP_IDEMPOTENCY_CONFLICT",
                "该请求编号已经用于另一份行程草稿。",
                status_code=409,
                details={"client_request_id": str(payload.client_request_id)},
            )
        return TripCreateOut(status="existing", trip=_detail_out(existing))

    end_date = (
        payload.start_date + timedelta(days=payload.day_count - 1)
        if payload.start_date is not None
        else None
    )
    trip = Trip(
        user_id=user.id,
        client_request_id=payload.client_request_id,
        request_fingerprint=fingerprint,
        title=payload.title,
        status="draft",
        origin_city_name=payload.origin_city_name,
        origin_city_adcode=payload.origin_city_adcode,
        destination_city_name=payload.destination_city_name,
        destination_city_adcode=payload.destination_city_adcode,
        start_date=payload.start_date,
        end_date=end_date,
        day_count=payload.day_count,
        timezone=payload.timezone,
        party_type=payload.party_type,
        pace=payload.pace,
        interests=payload.interests,
        transport_modes=payload.transport_modes,
        dietary_constraints=payload.dietary_constraints,
        total_budget_yuan=payload.total_budget_yuan,
        daily_start_time=payload.daily_start_time,
        daily_end_time=payload.daily_end_time,
        requirements_snapshot=payload.requirements_snapshot,
    )
    for day_number in range(1, payload.day_count + 1):
        trip.days.append(
            TripDay(
                day_number=day_number,
                travel_date=(
                    payload.start_date + timedelta(days=day_number - 1)
                    if payload.start_date is not None
                    else None
                ),
                status="draft",
                start_time=payload.daily_start_time,
                end_time=payload.daily_end_time,
                walking_intensity="unknown",
            )
        )
    db.add(trip)
    db.commit()

    created = _require_trip(db, trip.id, payload.username)
    return TripCreateOut(status="created", trip=_detail_out(created))


@router.get("", response_model=TripListOut)
def list_trips(
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
    status: Annotated[TripStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TripListOut:
    user = _require_user(db, username)
    filters = [Trip.user_id == user.id]
    if status is not None:
        filters.append(Trip.status == status)
    total = db.scalar(select(func.count(Trip.id)).where(*filters)) or 0
    trips = db.scalars(
        select(Trip)
        .options(selectinload(Trip.user))
        .where(*filters)
        .order_by(Trip.updated_at.desc(), Trip.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return TripListOut(
        items=[_summary_out(trip) for trip in trips],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{trip_id}", response_model=TripDetailOut)
def get_trip(
    trip_id: Annotated[uuid.UUID, Path()],
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Query(min_length=1, max_length=64)] = "AuroraRovella",
) -> TripDetailOut:
    return _detail_out(_require_trip(db, trip_id, username))
