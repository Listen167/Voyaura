import json
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from itertools import pairwise, zip_longest
from typing import TypeVar

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.agent.guide_stays import attraction_key
from app.errors import AppError
from app.integrations.amap import AMapClient, AMapPoi

T = TypeVar("T")
ATTRACTION_TYPES = "110000|140100|140200"
SUPPORT_FACILITY = re.compile(
    r"停车场|停车库|停车点|泊车|售票|检票|出入口|地铁站|公交站|充电站|卫生间|公共厕所|"
    r"游客(?:服务|接待)中心|服务台|管理处|办公区|(?:出口|入口|[东西南北]门)$|"
    r"[-·—－][东西南北](?:侧)?广场$|(?:景区|公园|动物园|景点|塔)[东西南北](?:侧)?广场$"
)
ATTRACTION_SUBAREA = re.compile(
    r"^(?:[-·—－（(]|景区|旅游区|观景|观光|[A-Z0-9]+区|摩天轮|体验区|[东西南北](?:侧)?$)"
)


class AgentSettings(BaseSettings):
    llm_enabled: bool = False
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VOYAURA_AGENT_", extra="ignore")
    confirmation_ttl_seconds: int = Field(default=600, ge=30, le=1800)
    run_timeout_seconds: int = Field(default=300, ge=60, le=900)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ToolTrace:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def add(
        self,
        stage: str,
        tool: str,
        status: str,
        message: str,
        *,
        attempt: int = 1,
        details: dict | None = None,
        duration_ms: int | None = None,
    ) -> None:
        item = {
            "sequence": len(self.events) + 1,
            "at": now_iso(),
            "stage": stage,
            "tool": tool,
            "status": status,
            "message": message,
            "attempt": attempt,
        }
        if details:
            item["details"] = details
        if duration_ms is not None:
            item["duration_ms"] = duration_ms
        self.events.append(item)

    def call(self, tool: str, function: Callable[[], T]) -> T | None:
        for attempt in (1, 2):
            start = time.monotonic()
            self.add("tool", tool, "running", "执行白名单工具。", attempt=attempt)
            try:
                result = function()
            except AppError as error:
                self.add(
                    "tool",
                    tool,
                    "error",
                    error.message,
                    attempt=attempt,
                    details={"code": error.code, "retryable": error.retryable},
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                if error.retryable and attempt == 1:
                    self.add("recovery", tool, "retrying", "可恢复错误，仅重试一次。")
                    if error.code == "AMAP_RATE_LIMIT":
                        time.sleep(1)
                    continue
                return None
            except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
                self.add(
                    "tool",
                    tool,
                    "error",
                    "工具响应不可用，已保留未知状态。",
                    attempt=attempt,
                    details={"code": "AGENT_TOOL_INVALID_RESPONSE"},
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                return None
            self.add(
                "tool",
                tool,
                "succeeded",
                "工具返回可解析结果。",
                attempt=attempt,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
            return result
        return None


def local_intent(request: dict) -> list[str]:
    explicit = request["must_visit"] + request["interests"]
    if explicit:
        return list(dict.fromkeys(explicit))[:3]
    # A narrow, declared rule set, never marketed as understanding arbitrary language.
    goal = request["goal"]
    topics = [
        word
        for word in ("博物馆", "公园", "美术馆", "古镇", "历史", "美食", "海边")
        if word in goal
    ]
    return topics[:3] or ["风景名胜"]


def model_intent(request: dict, trace: ToolTrace, settings: AgentSettings) -> list[str] | None:
    if not (settings.llm_enabled and settings.llm_api_key):
        trace.add(
            "intent",
            "deepseek",
            "unavailable",
            "外部模型未启用或未配置；保留本地规则结果。",
            details={"code": "MODEL_CONFIGURATION_REQUIRED"},
        )
        return None

    def call() -> list[str]:
        # A fixed allowlisted endpoint. No user-specified URLs or private history sent.
        with httpx.Client(timeout=20.0, trust_env=False) as client:
            response = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": 0,
                    "max_tokens": 250,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                '仅从用户旅行目标抽取最多3个景点检索关键词，返回JSON {"keywords":["词"]}。'
                                "不能输出坐标、票价、营业时间、工具调用或执行动作。不确定则空数组。"
                            ),
                        },
                        {"role": "user", "content": request["city_name"] + "：" + request["goal"]},
                    ],
                },
            )
        if response.status_code != 200:
            raise AppError(
                "MODEL_PROVIDER_ERROR",
                "模型服务失败，回退至本地规则。",
                retryable=response.status_code in (429, 500, 502, 503, 504),
            )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise TypeError("Structured intent must be an object")
        words = parsed.get("keywords")
        if not isinstance(words, list) or len(words) > 3:
            raise ValueError("Invalid structured intent")
        if any(not isinstance(w, str) or not w.strip() or len(w) > 80 for w in words):
            raise ValueError("Invalid topic")
        return [w.strip() for w in words]

    return trace.call("deepseek.extract_search_topics", call)


def valid_coordinates(longitude: float, latitude: float) -> bool:
    return (
        math.isfinite(longitude)
        and math.isfinite(latitude)
        and 73 <= longitude <= 136
        and 3 <= latitude <= 54
    )


def is_visitable_attraction(poi: AMapPoi) -> bool:
    if SUPPORT_FACILITY.search(poi.name) or SUPPORT_FACILITY.search(poi.category):
        return False
    return any(
        code.startswith("11") or code[:4] in ("1401", "1402")
        for code in poi.typecode.split("|")
    )


def is_subarea_of(name: str, main_name: str) -> bool:
    return name != main_name and name.startswith(main_name) and bool(
        ATTRACTION_SUBAREA.match(name[len(main_name):])
    )


def preferred_attraction_matches(name: str, items: list[AMapPoi]) -> list[AMapPoi]:
    if any(poi.name == name for poi in items):
        return [poi for poi in items if not is_subarea_of(poi.name, name)]
    return items


def attraction_stay(poi: AMapPoi, pace: str) -> int:
    label = poi.category + poi.name
    if any(word in label for word in ("动物园", "植物园", "主题公园", "湿地")):
        return 150 if pace == "relaxed" else 120
    if any(word in label for word in ("博物馆", "博物院", "美术馆", "公园", "古镇")):
        return 105 if pace == "relaxed" else 90
    if any(word in label for word in ("广场", "寺庙", "道观", "纪念碑")):
        return 60 if pace == "relaxed" else 45
    return 90 if pace == "relaxed" else 75


def match_attraction(name: str, candidates: list[dict]) -> list[dict]:
    exact = [candidate for candidate in candidates if attraction_key(candidate["name"]) == attraction_key(name)]
    return exact or [candidate for candidate in candidates if name in candidate["name"]]


def deduplicate(candidates: list[dict]) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for candidate in candidates:
        key = (
            candidate["name"].casefold().replace(" ", ""),
            round(candidate["longitude"], 4),
            round(candidate["latitude"], 4),
        )
        if key not in unique:
            unique[key] = candidate.copy()
        else:
            unique[key]["must_visit"] |= candidate["must_visit"]
    return list(unique.values())


def amap_candidate(poi: AMapPoi, request: dict, trace: ToolTrace, *, required: bool = False) -> dict | None:
    if not valid_coordinates(poi.longitude, poi.latitude):
        trace.add("evidence", "candidate_gate", "rejected", "地点坐标不合法或非有限值。")
        return None
    if not poi.id or not poi.name:
        return None
    explicit_campus = "141201" in poi.typecode.split("|") and not SUPPORT_FACILITY.search(poi.name) and any(
        ("大学" in name and ("校园" in name or "校区" in name))
        and attraction_key(name) == attraction_key(poi.name)
        for name in request["must_visit"]
    )
    if not is_visitable_attraction(poi) and not explicit_campus:
        trace.add(
            "evidence", "candidate_gate", "rejected", "剔除交通、售票或其他附属设施。",
            details={"typecode": poi.typecode},
        )
        return None
    if AMapClient._city_adcode(poi.adcode) != request["city_adcode"]:
        trace.add("evidence", "candidate_gate", "rejected", "地点行政区不属于请求城市。")
        return None
    window = re.fullmatch(
        r"([0-2]\d:[0-5]\d)\s*[-—~]\s*([0-2]\d:[0-5]\d)", poi.opening_hours or ""
    )
    opening_start = opening_end = None
    if window and window[1] < window[2] and window[2] < "24:00":
        opening_start, opening_end = window.groups()
    return {
        "id": "amap:" + poi.id,
        "name": poi.name,
        "address": poi.address,
        "longitude": poi.longitude,
        "latitude": poi.latitude,
        "source": "amap",
        "verification": "verified",
        "source_url": "https://uri.amap.com/marker?poiid=" + poi.id,
        "queried_at": now_iso(),
        "stay_minutes": attraction_stay(poi, request["pace"]),
        "stay_source": "planning_assumption",
        "opening_start": opening_start,
        "opening_end": opening_end,
        "cost_yuan": None,
        "must_visit": required,
    }


def collect_candidates(
    request: dict, client: AMapClient, trace: ToolTrace, topics: list[str]
) -> list[dict]:
    candidates = []
    for index, supplied in enumerate(request["candidates"]):
        candidates.append(
            {
                **supplied,
                "id": f"user-{index + 1}",
                "source": "user_provided",
                "verification": "user_provided",
                "source_url": None,
                "queried_at": now_iso(),
                "stay_source": "user_provided",
            }
        )
    original_count = len(candidates)
    candidates = deduplicate(candidates)
    selected = request.get("selected_pois", [])
    if candidates and not selected:
        trace.add(
            "evidence",
            "user_input",
            "accepted",
            "已读取用户提供候选，标记为未经独立核验。",
            details={
                "count": len(candidates),
                "duplicates_removed": original_count - len(candidates),
            },
        )
    if not request["allow_external"]:
        trace.add("permission", "amap", "skipped", "未授权外部服务，未调用高德。")
        return candidates
    if candidates and not selected:
        trace.add(
            "evidence",
            "candidate_snapshot",
            "frozen",
            "使用用户给定候选池，不扩增地点；按授权查询交通。",
        )
        return candidates
    if not client.key:
        trace.add(
            "tool",
            "amap.search_poi",
            "unavailable",
            "高德Web服务未配置；不会生成伪造地点。",
            details={"code": "AMAP_KEY_MISSING"},
        )
        return candidates
    verified = []
    seen: set[str] = set()
    for selection in selected:
        poi_id = selection["id"]
        if poi_id in seen:
            continue
        poi = trace.call("amap.get_poi_detail", lambda poi_id=poi_id: client.get_poi_detail(poi_id))
        if poi and poi.id == poi_id:
            candidate = amap_candidate(poi, request, trace, required=True)
            if candidate:
                verified.append(candidate)
                seen.add(poi_id)
    candidates = deduplicate(verified + candidates)
    page_size = min(16, max(8, request["days"] * (request.get("stops_per_day") or 4)))
    topic_candidates = []
    for topic in topics[:3]:
        if len(candidates) >= 12:
            break
        response = trace.call(
            "amap.search_poi",
            lambda topic=topic: client.search_pois(
                keywords=topic,
                adcode=request["city_adcode"],
                category="141201" if "大学" in topic and ("校园" in topic or "校区" in topic) else ATTRACTION_TYPES,
                page_size=page_size,
            ),
        )
        if response is None:
            continue
        pois, _ = response
        matches = []
        for poi in preferred_attraction_matches(topic, pois):
            if poi.id in seen:
                continue
            candidate = amap_candidate(poi, request, trace)
            if candidate and not any(word in poi.name for word in request.get("avoid_places", [])):
                seen.add(poi.id)
                matches.append(candidate)
        topic_candidates.append(matches)
    for batch in zip_longest(*topic_candidates):
        candidates.extend(candidate for candidate in batch if candidate is not None)
    candidates = deduplicate(candidates)
    for name in request["must_visit"]:
        matches = match_attraction(name, candidates)
        if len(matches) == 1:
            matches[0]["must_visit"] = True
    # Keep distinct venues across themes. A sub-location of an already represented
    # attraction is only retained if the user explicitly selected it.
    main_names = {c["name"] for c in candidates}
    candidates = [
        c for c in candidates
        if c["must_visit"] or not any(is_subarea_of(c["name"], main) for main in main_names)
    ]
    return sorted(candidates, key=lambda c: not c["must_visit"])[:12]


def collect_legs(
    request: dict, groups: list[list[dict]], client: AMapClient, trace: ToolTrace
) -> list[dict]:
    legs = []
    for group in groups:
        for origin, destination in pairwise(group):
            leg = {
                "from_id": origin["id"],
                "to_id": destination["id"],
                "duration_minutes": None,
                "distance_meters": None,
                "source": "unknown",
                "queried_at": None,
            }
            if request["allow_external"] and client.key:
                result = trace.call(
                    "amap.get_route",
                    lambda origin=origin, destination=destination: client.plan_route(
                        mode=request["transport"],
                        origin=(origin["longitude"], origin["latitude"]),
                        destination=(destination["longitude"], destination["latitude"]),
                        origin_adcode=request["city_adcode"],
                        destination_adcode=request["city_adcode"],
                    ),
                )
                if result and result[0]:
                    route = result[0][0]
                    duration, meters = route.duration_seconds, route.distance_meters
                    if (
                        isinstance(duration, (int, float))
                        and math.isfinite(duration)
                        and 0 < duration <= 24 * 3600
                        and isinstance(meters, (int, float))
                        and math.isfinite(meters)
                        and meters > 0
                    ):
                        leg.update(
                            duration_minutes=math.ceil(duration / 60),
                            distance_meters=meters,
                            source="amap",
                            queried_at=now_iso(),
                            mode=request["transport"],
                            instructions=[step.instruction for step in route.steps if step.instruction][:6],
                        )
                    else:
                        trace.add(
                            "evidence",
                            "route_gate",
                            "rejected",
                            "交通耗时或距离无效，仍为未知。",
                            details={"code": "AMAP_ROUTE_INVALID_EVIDENCE"},
                        )
            legs.append(leg)
    return legs
