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

    def _city_name(self, address: dict[str, Any]) -> str:
        return (
            self._text(address.get("city"))
            or self._text(address.get("province"))
            or self._text(address.get("district"))
        )


@lru_cache
def get_amap_client() -> AMapClient:
    return AMapClient(settings.amap_web_key, settings.amap_web_private_key)
