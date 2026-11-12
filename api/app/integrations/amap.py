from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.errors import AppError

AMAP_BASE_URL = "https://restapi.amap.com"
MUNICIPALITY_PREFIXES = {"11", "12", "31", "50", "81", "82"}

AMAP_ERROR_MAP: dict[str, tuple[str, str, bool]] = {
    "10001": ("AMAP_INVALID_KEY", "高德 Web 服务 Key 不正确或已过期。", False),
    "10002": ("AMAP_SERVICE_UNAVAILABLE", "当前 Key 没有请求该高德服务的权限。", False),
    "10003": ("AMAP_DAILY_LIMIT", "高德服务今日调用额度已用完。", True),
    "10004": ("AMAP_RATE_LIMIT", "高德服务调用过于频繁，请稍后重试。", True),
    "10005": ("AMAP_IP_NOT_ALLOWED", "当前服务器出口 IP 不在高德白名单中。", False),
    "10006": ("AMAP_DOMAIN_NOT_ALLOWED", "当前域名不在高德 Key 白名单中。", False),
    "10007": (
        "AMAP_INVALID_SIGNATURE",
        "高德 Web 服务开启了数字签名，但本次请求未通过签名验证。",
        False,
    ),
    "10009": ("AMAP_PLATFORM_MISMATCH", "高德 Key 类型与 Web 服务接口不匹配。", False),
    "10012": ("AMAP_INSUFFICIENT_PRIVILEGES", "高德 Key 权限不足。", False),
    "10016": ("AMAP_SERVER_BUSY", "高德服务负载较高，请稍后重试。", True),
    "20000": ("AMAP_INVALID_PARAMS", "高德服务拒绝了无效参数。", False),
    "20011": ("AMAP_OUTSIDE_CHINA", "当前位置不在高德境内服务范围内。", False),
}


@dataclass(frozen=True)
class ResolvedCity:
    adcode: str
    name_zh: str
    province_zh: str
    longitude: float
    latitude: float
    formatted_address: str
    gcj_longitude: float
    gcj_latitude: float


@dataclass(frozen=True)
class AMapPoi:
    id: str
    name: str
    category: str
    typecode: str
    address: str
    province: str
    city: str
    district: str
    adcode: str
    longitude: float
    latitude: float
    telephone: str | None = None
    rating: str | None = None
    average_cost: str | None = None
    opening_hours: str | None = None


@dataclass(frozen=True)
class AMapRouteStep:
    instruction: str
    distance_meters: int
    duration_seconds: int | None = None
    road_name: str | None = None
    transport: str = "walk"


@dataclass(frozen=True)
class AMapRouteOption:
    distance_meters: int
    duration_seconds: int
    steps: tuple[AMapRouteStep, ...]
    walking_distance_meters: int | None = None
    tolls_yuan: float | None = None
    taxi_cost_yuan: float | None = None


class AMapClient:
    def __init__(self, key: str, private_key: str = "", timeout_seconds: float = 8.0) -> None:
        self.key = key
        self.private_key = private_key
        self.timeout_seconds = timeout_seconds

    def resolve_wgs84_city(self, longitude: float, latitude: float) -> ResolvedCity:
        if not self.key:
            raise AppError(
                "AMAP_KEY_MISSING",
                "后端尚未配置高德 Web 服务 Key。",
                status_code=503,
            )

        gcj_longitude, gcj_latitude = self._convert_wgs84(longitude, latitude)
        regeo = self._request(
            "/v3/geocode/regeo",
            {
                "location": f"{gcj_longitude:.6f},{gcj_latitude:.6f}",
                "extensions": "base",
                "radius": "1000",
            },
        ).get("regeocode", {})
        address = regeo.get("addressComponent") or {}
        district_adcode = str(address.get("adcode") or "")
        if len(district_adcode) != 6:
            raise AppError(
                "AMAP_CITY_NOT_FOUND",
                "高德没有返回可识别的中国行政区代码。",
                status_code=422,
                details={"provider_adcode": district_adcode},
            )

        city_adcode = self._city_adcode(district_adcode)
        district = self._request(
            "/v3/config/district",
            {"keywords": city_adcode, "subdistrict": "0", "extensions": "base"},
        )
        district_list = district.get("districts") or []
        if not district_list:
            raise AppError(
                "AMAP_CITY_NOT_FOUND",
                "高德没有返回对应城市信息。",
                status_code=422,
                details={"adcode": city_adcode},
            )

        city = district_list[0]
        center_longitude, center_latitude = self._parse_location(str(city.get("center") or ""))
        province = self._text(address.get("province")) or self._text(city.get("name"))
        return ResolvedCity(
            adcode=str(city.get("adcode") or city_adcode),
            name_zh=self._text(city.get("name")) or self._city_name(address),
            province_zh=province,
            longitude=center_longitude,
            latitude=center_latitude,
            formatted_address=self._text(regeo.get("formatted_address")),
            gcj_longitude=gcj_longitude,
            gcj_latitude=gcj_latitude,
        )

    def search_pois(
        self,
        *,
        keywords: str,
        adcode: str,
        category: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[AMapPoi], int]:
        if not self.key:
            raise AppError(
                "AMAP_KEY_MISSING",
                "后端尚未配置高德 Web 服务 Key。",
                status_code=503,
            )
        payload = self._request(
            "/v5/place/text",
            {
                "keywords": keywords,
                "region": adcode,
                "city_limit": "true",
                "types": category,
                "page_num": str(page),
                "page_size": str(page_size),
                "show_fields": "business",
            },
        )
        items = []
        for raw_poi in payload.get("pois") or []:
            if not isinstance(raw_poi, dict):
                continue
            try:
                items.append(self._poi_from_payload(raw_poi))
            except AppError:
                continue
        return items, self._integer(payload.get("count"), default=len(items))

    def get_poi_detail(self, poi_id: str) -> AMapPoi:
        if not self.key:
            raise AppError(
                "AMAP_KEY_MISSING",
                "后端尚未配置高德 Web 服务 Key。",
                status_code=503,
            )
        payload = self._request(
            "/v5/place/detail",
            {"id": poi_id, "show_fields": "business"},
        )
        pois = payload.get("pois") or []
        if not pois or not isinstance(pois[0], dict):
            raise AppError(
                "AMAP_POI_NOT_FOUND",
                "高德没有返回对应地点详情。",
                status_code=404,
                details={"poi_id": poi_id},
            )
        return self._poi_from_payload(pois[0])

    def plan_route(
        self,
        *,
        mode: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
        origin_adcode: str | None = None,
        destination_adcode: str | None = None,
    ) -> tuple[list[AMapRouteOption], float | None]:
        if not self.key:
            raise AppError(
                "AMAP_KEY_MISSING",
                "后端尚未配置高德 Web 服务 Key。",
                status_code=503,
            )
        paths = {
            "walking": "/v5/direction/walking",
            "driving": "/v5/direction/driving",
            "transit": "/v5/direction/transit/integrated",
        }
        if mode not in paths:
            raise AppError(
                "ROUTE_MODE_UNSUPPORTED",
                "当前不支持这种市内路线方式。",
                status_code=422,
                details={"mode": mode},
            )
        params = {
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{destination[0]:.6f},{destination[1]:.6f}",
            "show_fields": "cost,navi",
        }
        if mode == "transit":
            if not origin_adcode or not destination_adcode:
                raise AppError(
                    "ROUTE_TRANSIT_ADCODE_REQUIRED",
                    "公交地铁路线需要起点和终点城市代码。",
                    status_code=422,
                )
            params.update({"city1": origin_adcode, "city2": destination_adcode})

        payload = self._request(paths[mode], params)
        route = payload.get("route")
        if not isinstance(route, dict):
            route = {}
        raw_options = route.get("transits" if mode == "transit" else "paths")
        options = [
            self._route_option_from_payload(item, mode=mode, route=route)
            for item in self._dict_items(raw_options)
        ]
        if not options:
            raise AppError(
                "AMAP_ROUTE_NOT_FOUND",
                "高德没有返回可用路线。",
                status_code=404,
                details={"mode": mode},
            )
        taxi_cost = self._optional_number(route.get("taxi_cost"))
        return options, taxi_cost

    @staticmethod
    def poi_navigation_url(poi: AMapPoi) -> str:
        params = urlencode(
            {
                "position": f"{poi.longitude:.6f},{poi.latitude:.6f}",
                "name": poi.name,
                "src": "voyaura",
                "coordinate": "gaode",
                "callnative": "0",
            }
        )
        return f"https://uri.amap.com/marker?{params}"

    def _convert_wgs84(self, longitude: float, latitude: float) -> tuple[float, float]:
        payload = self._request(
            "/v3/assistant/coordinate/convert",
            {"locations": f"{longitude:.6f},{latitude:.6f}", "coordsys": "gps"},
        )
        return self._parse_location(str(payload.get("locations") or ""))

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        request_params = {**params, "key": self.key, "output": "JSON"}
        if self.private_key:
            signature_source = urlencode(sorted(request_params.items()), safe=",")
            request_params["sig"] = hashlib.md5(
                f"{signature_source}{self.private_key}".encode()
            ).hexdigest()

        try:
            response = httpx.get(
                f"{AMAP_BASE_URL}{path}",
                params=request_params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except ImportError as exc:
            raise AppError(
                "AMAP_PROXY_CONFIG_ERROR",
                "系统启用了代理，但后端缺少对应的代理传输依赖。",
                status_code=503,
                details={"dependency": "httpx[socks]"},
            ) from exc
        except httpx.TimeoutException as exc:
            raise AppError(
                "AMAP_TIMEOUT",
                "连接高德服务超时，请稍后重试。",
                status_code=504,
                retryable=True,
            ) from exc
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise AppError(
                "AMAP_NETWORK_ERROR",
                "无法连接高德服务，请检查网络后重试。",
                status_code=502,
                retryable=True,
            ) from exc

        if str(payload.get("status")) != "1":
            infocode = str(payload.get("infocode") or "unknown")
            code, message, retryable = AMAP_ERROR_MAP.get(
                infocode,
                ("AMAP_PROVIDER_ERROR", "高德服务返回了未识别的错误。", False),
            )
            raise AppError(
                code,
                message,
                status_code=502,
                details={"provider_infocode": infocode, "provider_info": payload.get("info")},
                retryable=retryable,
            )
        return payload

    @staticmethod
    def _city_adcode(adcode: str) -> str:
        if adcode[:2] in MUNICIPALITY_PREFIXES:
            return f"{adcode[:2]}0000"
        return f"{adcode[:4]}00"

    @staticmethod
    def _parse_location(value: str) -> tuple[float, float]:
        try:
            longitude, latitude = value.split(",", 1)
            return float(longitude), float(latitude)
        except (TypeError, ValueError) as exc:
            raise AppError(
                "AMAP_COORDINATE_INVALID",
                "高德返回了无法解析的坐标。",
                status_code=502,
            ) from exc

    @staticmethod
    def _text(value: Any) -> str:
        return value if isinstance(value, str) else ""

    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        text = cls._text(value).strip()
        return text or None

    @staticmethod
    def _integer(value: Any, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_number(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dict_items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @classmethod
    def _route_option_from_payload(
        cls,
        payload: dict[str, Any],
        *,
        mode: str,
        route: dict[str, Any],
    ) -> AMapRouteOption:
        cost = payload.get("cost")
        if not isinstance(cost, dict):
            cost = {}
        raw_steps = (
            cls._transit_steps(payload.get("segments"))
            if mode == "transit"
            else cls._route_steps(payload.get("steps"), transport=mode)
        )
        duration = cls._integer(cost.get("duration") or payload.get("duration"))
        taxi_cost = cls._optional_number(payload.get("taxi_cost") or route.get("taxi_cost"))
        return AMapRouteOption(
            distance_meters=cls._integer(payload.get("distance")),
            duration_seconds=duration,
            steps=tuple(raw_steps),
            walking_distance_meters=(
                cls._integer(payload.get("walking_distance")) if mode == "transit" else None
            ),
            tolls_yuan=cls._optional_number(cost.get("tolls") or payload.get("tolls")),
            taxi_cost_yuan=taxi_cost,
        )

    @classmethod
    def _route_steps(cls, value: Any, *, transport: str) -> list[AMapRouteStep]:
        steps = []
        for item in cls._dict_items(value):
            cost = item.get("cost")
            if not isinstance(cost, dict):
                cost = {}
            instruction = cls._text(item.get("instruction")).strip()
            if not instruction:
                continue
            steps.append(
                AMapRouteStep(
                    instruction=instruction,
                    distance_meters=cls._integer(item.get("step_distance") or item.get("distance")),
                    duration_seconds=(
                        cls._integer(cost.get("duration")) if cost.get("duration") else None
                    ),
                    road_name=cls._optional_text(item.get("road_name") or item.get("road")),
                    transport=transport,
                )
            )
        return steps

    @classmethod
    def _transit_steps(cls, value: Any) -> list[AMapRouteStep]:
        steps: list[AMapRouteStep] = []
        for segment in cls._dict_items(value):
            walking = segment.get("walking")
            if isinstance(walking, dict):
                steps.extend(cls._route_steps(walking.get("steps"), transport="walk"))
            bus = segment.get("bus")
            if isinstance(bus, dict):
                for line in cls._dict_items(bus.get("buslines")):
                    departure = line.get("departure_stop")
                    arrival = line.get("arrival_stop")
                    start = cls._text(departure.get("name")) if isinstance(departure, dict) else ""
                    end = cls._text(arrival.get("name")) if isinstance(arrival, dict) else ""
                    name = cls._text(line.get("name")).split("(", 1)[0].strip() or "公交/地铁"
                    instruction = f"乘坐{name}"
                    if start and end:
                        instruction += f"，从{start}到{end}"
                    steps.append(
                        AMapRouteStep(
                            instruction=instruction,
                            distance_meters=cls._integer(line.get("distance")),
                            duration_seconds=(
                                cls._integer(line.get("duration")) if line.get("duration") else None
                            ),
                            transport="transit",
                        )
                    )
            railway = segment.get("railway")
            if isinstance(railway, dict) and railway:
                name = cls._text(railway.get("name") or railway.get("trip")).strip() or "铁路"
                steps.append(
                    AMapRouteStep(
                        instruction=f"乘坐{name}",
                        distance_meters=cls._integer(railway.get("distance")),
                        duration_seconds=(
                            cls._integer(railway.get("time")) if railway.get("time") else None
                        ),
                        transport="railway",
                    )
                )
        return steps

    @classmethod
    def _poi_from_payload(cls, payload: dict[str, Any]) -> AMapPoi:
        poi_id = cls._text(payload.get("id")).strip()
        name = cls._text(payload.get("name")).strip()
        if not poi_id or not name:
            raise AppError(
                "AMAP_POI_INVALID",
                "高德返回的地点缺少 ID 或名称。",
                status_code=502,
            )
        longitude, latitude = cls._parse_location(cls._text(payload.get("location")))
        business = payload.get("business")
        if not isinstance(business, dict):
            business = {}
        return AMapPoi(
            id=poi_id,
            name=name,
            category=cls._text(payload.get("type")),
            typecode=cls._text(payload.get("typecode")),
            address=cls._text(payload.get("address")),
            province=cls._text(payload.get("pname")),
            city=cls._text(payload.get("cityname")),
            district=cls._text(payload.get("adname")),
            adcode=cls._text(payload.get("adcode")),
            longitude=longitude,
            latitude=latitude,
            telephone=cls._optional_text(business.get("tel")),
            rating=cls._optional_text(business.get("rating")),
            average_cost=cls._optional_text(business.get("cost")),
            opening_hours=cls._optional_text(business.get("opentime_today")),
        )

    def _city_name(self, address: dict[str, Any]) -> str:
        return (
            self._text(address.get("city"))
            or self._text(address.get("province"))
            or self._text(address.get("district"))
        )


@lru_cache
def get_amap_client() -> AMapClient:
    return AMapClient(settings.amap_web_key, settings.amap_web_private_key)
