from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.integrations.amap import AMapClient, AMapPoi, get_amap_client
from app.schemas import PoiDetailOut, PoiOut, PoiSearchDraft, PoiSearchOut

router = APIRouter(prefix="/tools/poi", tags=["city-tools"])


def poi_out(client: AMapClient, poi: AMapPoi) -> PoiOut:
    return PoiOut(
        id=poi.id,
        name=poi.name,
        category=poi.category,
        typecode=poi.typecode,
        address=poi.address,
        province=poi.province,
        city=poi.city,
        district=poi.district,
        adcode=poi.adcode,
        longitude=poi.longitude,
        latitude=poi.latitude,
        telephone=poi.telephone,
        rating=poi.rating,
        average_cost=poi.average_cost,
        opening_hours=poi.opening_hours,
        navigation_url=client.poi_navigation_url(poi),
    )


@router.post("/search", response_model=PoiSearchOut)
def search_pois(
    payload: PoiSearchDraft,
    client: Annotated[AMapClient, Depends(get_amap_client)],
) -> PoiSearchOut:
    keywords = payload.keywords.strip()
    items, total = client.search_pois(
        keywords=keywords,
        adcode=payload.city_adcode,
        category=payload.category.strip(),
        page=payload.page,
        page_size=payload.page_size,
    )
    return PoiSearchOut(
        keywords=keywords,
        city_adcode=payload.city_adcode,
        total=total,
        page=payload.page,
        page_size=payload.page_size,
        items=[poi_out(client, item) for item in items],
        queried_at=datetime.now(UTC),
    )


@router.get("/{poi_id}", response_model=PoiDetailOut)
def get_poi_detail(
    poi_id: Annotated[str, Path(min_length=1, max_length=128)],
    client: Annotated[AMapClient, Depends(get_amap_client)],
) -> PoiDetailOut:
    item = client.get_poi_detail(poi_id)
    return PoiDetailOut(
        item=poi_out(client, item),
        queried_at=datetime.now(UTC),
    )
