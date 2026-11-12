from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.integrations.amap import AMapClient, get_amap_client
from app.schemas import (
    LocalRouteDraft,
    LocalRouteOut,
    RouteCapabilitiesOut,
    RouteOptionOut,
    RouteProviderCapabilityOut,
    RouteStepOut,
)

router = APIRouter(prefix="/tools/routes", tags=["city-tools"])


@router.get("/capabilities", response_model=RouteCapabilitiesOut)
def get_route_capabilities(
    client: Annotated[AMapClient, Depends(get_amap_client)],
) -> RouteCapabilitiesOut:
    amap_available = bool(client.key)
    amap_state = "available" if amap_available else "configuration_required"
    local_specs: tuple[
        tuple[Literal["walking", "transit", "driving"], list[str]], ...
    ] = (
        ("walking", ["distance", "duration", "steps"]),
        ("transit", ["bus", "metro", "walking_transfer", "duration"]),
        ("driving", ["distance", "duration", "tolls", "steps"]),
    )
    local = [
        RouteProviderCapabilityOut(
            mode=mode,
            provider="amap",
            available=amap_available,
            state=amap_state,
            data_scope=scope,
            application_url="https://lbs.amap.com/",
            notice=(
                "高德 Web 服务已配置；若返回 10007，仍需修正数字签名设置。"
                if amap_available
                else "需要在 API 环境配置高德 Web 服务 Key。"
            ),
        )
        for mode, scope in local_specs
    ]
    intercity = [
        RouteProviderCapabilityOut(
            mode="high_speed_rail",
            provider="licensed_rail_partner",
            available=False,
            state="partner_required",
            data_scope=["train_number", "schedule", "seat_class", "price", "availability"],
            application_url="https://open.ctrip.com/",
            notice="12306 没有面向本项目的稳定公开票务 API；需接入携程、同程等正式合作接口。",
        ),
        RouteProviderCapabilityOut(
            mode="train",
            provider="licensed_rail_partner",
            available=False,
            state="partner_required",
            data_scope=["train_number", "schedule", "seat_class", "price", "availability"],
            application_url="https://open.ctrip.com/",
            notice="普通列车与高铁共用授权铁路 Provider，不抓取 12306 网页或未公开接口。",
        ),
        RouteProviderCapabilityOut(
            mode="flight",
            provider="amadeus_or_china_licensed_partner",
            available=False,
            state="partner_required",
            data_scope=["flight_number", "schedule", "fare", "cabin", "availability"],
            application_url="https://developers.amadeus.com/",
            notice="开发期可申请 Amadeus；国内生产需评估航司覆盖并接入携程或中航信类授权源。",
        ),
    ]
    return RouteCapabilitiesOut(local=local, intercity=intercity, queried_at=datetime.now(UTC))


@router.post("/plan", response_model=LocalRouteOut)
def plan_local_route(
    payload: LocalRouteDraft,
    client: Annotated[AMapClient, Depends(get_amap_client)],
) -> LocalRouteOut:
    options, _ = client.plan_route(
        mode=payload.mode,
        origin=(payload.origin.longitude, payload.origin.latitude),
        destination=(payload.destination.longitude, payload.destination.latitude),
        origin_adcode=payload.origin_adcode,
        destination_adcode=payload.destination_adcode,
    )
    return LocalRouteOut(
        mode=payload.mode,
        origin=payload.origin,
        destination=payload.destination,
        queried_at=datetime.now(UTC),
        options=[
            RouteOptionOut(
                distance_meters=option.distance_meters,
                duration_seconds=option.duration_seconds,
                walking_distance_meters=option.walking_distance_meters,
                tolls_yuan=option.tolls_yuan,
                taxi_cost_yuan=option.taxi_cost_yuan,
                steps=[
                    RouteStepOut(
                        instruction=step.instruction,
                        distance_meters=step.distance_meters,
                        duration_seconds=step.duration_seconds,
                        road_name=step.road_name,
                        transport=step.transport,
                    )
                    for step in option.steps
                ],
            )
            for option in options
        ],
    )
