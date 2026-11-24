"""Structured travel turns and a small local city guide."""

import json
import re
from typing import Literal

from langchain_deepseek import ChatDeepSeek
from pydantic import Field, SecretStr

from app.agent.schemas import StrictModel
from app.agent.tools import AgentSettings, ToolTrace
from app.config import settings
from app.errors import AppError

CITY_GUIDES = {
    "440100": ("广州市", ["越秀公园", "沙面", "广州动物园"], "老城建筑、珠江沿岸和动物园可分开安排。"),
    "330100": ("杭州市", ["西湖", "灵隐寺", "西溪湿地"], "西湖、灵隐和西溪可按片区安排，减少跨区往返。"),
    "310000": ("上海市", ["外滩", "豫园", "上海博物馆"], "可按滨江、老城和博物馆选点。"),
    "110000": ("北京市", ["故宫博物院", "景山公园", "颐和园"], "可把中轴线与西郊园林分开安排。"),
    "510100": ("成都市", ["成都大熊猫繁育研究基地", "杜甫草堂", "金沙遗址博物馆"], "可按熊猫、古迹和博物馆选点。"),
    "350200": ("厦门市", ["鼓浪屿", "厦门园林植物园", "沙坡尾"], "岛上步行与本岛行程适合分别安排。"),
}
NUMBERS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}
COUNT = r"(\d{1,2}|[一二两三四五六七八九十])"


class TravelTurn(StrictModel):
    city_name: str | None = Field(default=None, max_length=100)
    days: int | None = Field(default=None, ge=1, le=4)
    stops_per_day: int | None = Field(default=None, ge=1, le=4)
    rest_minutes: int | None = Field(default=None, ge=0, le=150)
    daily_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    transport: Literal["walking", "transit", "driving"] | None = None
    pace: Literal["relaxed", "balanced"] | None = None
    interests: list[str] | None = Field(default=None, max_length=3)
    must_visit: list[str] | None = Field(default=None, max_length=3)
    avoid_places: list[str] | None = Field(default=None, max_length=3)


def model_credentials() -> tuple[str, str]:
    agent = AgentSettings()
    if agent.llm_enabled and agent.llm_api_key.strip():
        return agent.llm_api_key, agent.llm_model
    return settings.deepseek_api_key.strip(), settings.deepseek_model


def model_turn(message: str, context: dict) -> TravelTurn:
    key, model = model_credentials()
    if not key:
        raise AppError("MODEL_CONFIGURATION_REQUIRED", "DeepSeek 尚未配置。", status_code=503)
    try:
        llm = ChatDeepSeek(
            api_key=SecretStr(key), model=model, temperature=0, timeout=20, max_retries=0,
            base_url=settings.deepseek_base_url,
        ).with_structured_output(TravelTurn, method="function_calling")
        result = llm.invoke([
            ("system", (
                "你是小曦。只提取当前消息明确修改的全程旅行条件，没提到的字段留空。"
                "不要把某一天的条件应用到全部天数。兴趣是景点检索主题，必去和排除只取用户原话。"
                "只有用户明确给出每天景点个数时才填写 stops_per_day。"
                "根据陪同者、体力和偏好判断 pace 或建议休息余量 rest_minutes，让规划器按实际时间决定景点数。"
                "城市必须是目的地。不要输出价格、开放时间、路线、坐标或工具调用。"
            )),
            ("human", json.dumps({"当前条件": context, "本轮要求": message}, ensure_ascii=False)),
        ])
    except Exception as exc:
        raise AppError("TRAVEL_MODEL_ERROR", "DeepSeek 暂时无法解析，尝试用本地规则。", status_code=502) from exc
    if not isinstance(result, TravelTurn):
        raise AppError("TRAVEL_MODEL_OUTPUT_INVALID", "DeepSeek 返回的条件无效。", status_code=502)
    return result


def number(text: str) -> int:
    return int(text) if text.isdigit() else NUMBERS[text]


def local_turn(message: str, cities: dict[str, str]) -> dict:
    fields = {}
    for name in sorted(cities.values(), key=len, reverse=True):
        if name.removesuffix("市") in message:
            fields["city_name"] = name
            break
    for field, pattern, label in (
        ("days", rf"(?<!第){COUNT}\s*(?:天|日)(?!开始|结束|早|晚|去)", "旅行天数"),
        ("stops_per_day", rf"每天[^，,。]{{0,10}}?{COUNT}\s*(?:个|处|站)", "每日景点数"),
    ):
        match = re.search(pattern, message)
        if match:
            value = number(match[1])
            if not 1 <= value <= 4:
                raise AppError("CHAT_RANGE_UNSUPPORTED", f"{label}目前支持 1 到 4。", status_code=422)
            fields[field] = value
    for pattern, mode in (("公交|地铁", "transit"), ("自驾|驾车", "driving"), ("步行", "walking")):
        if re.search(rf"(?<!不)(?<!不要)(?<!别用)(?:{pattern})", message):
            fields["transport"] = mode
            break
    if any(word in message for word in ("带娃", "带孩子", "带小孩", "带老人", "带长辈", "行动不便")):
        fields["pace"] = "relaxed"
        fields["rest_minutes"] = 90
    elif any(word in message for word in ("慢一点", "慢游", "轻松", "不赶", "别太累", "少走路")):
        fields["pace"] = "relaxed"
        fields["rest_minutes"] = 60
    elif any(word in message for word in ("紧凑", "多逛", "多安排", "丰富一点")):
        fields["pace"] = "balanced"
        fields["rest_minutes"] = 30
    topics = [word for word in ("博物馆", "动物园", "公园", "美术馆", "古镇", "湿地", "历史街区", "摄影", "海边")
              if re.search(rf"(?<!不要)(?<!不去)(?<!别去)(?<!去掉){word}", message)]
    if topics:
        fields["interests"] = topics[:3]
    for field, pattern in (
        ("must_visit", r"(?:一定(?:要)?去|必去|想去|我要去)\s*([^，,。；;！!？?\n]{2,24})"),
        ("avoid_places", r"(?:不要去|不去|别去|去掉|排除)\s*([^，,。；;！!？?\n]{2,24})"),
    ):
        names = [name.strip() for name in re.findall(pattern, message)]
        if field == "must_visit":
            names = [name for name in names if not any(
                re.fullmatch(rf"{re.escape(city.removesuffix('市'))}市?(?:玩|待)?{COUNT}?(?:天|日)?", name)
                for city in cities.values()
            )]
        if names:
            fields[field] = names[:3]
    if not re.search(r"第[0-9一二三四]天", message):
        pattern = rf"(上午|早上|下午|晚上)?\s*{COUNT}(?::([0-5]\d)|[点时](半)?)\s*(?:前|后)?\s*(开始|出发|结束|回来)"
        for period, hour, exact, half, verb in re.findall(pattern, message):
            value = number(hour)
            if period in ("下午", "晚上") and value < 12:
                value += 12
            if 0 <= value < 24:
                field = "daily_start" if verb in ("开始", "出发") else "daily_end"
                fields[field] = f"{value:02d}:{exact or ('30' if half else '00')}"
    return fields


def resolve_turn(request: dict, cities: dict[str, str], trace: ToolTrace) -> str:
    message = request["chat_message"]
    allowed = (*TravelTurn.model_fields, "start_date")
    context = {key: request[key] for key in allowed if key in request}
    fields = local_turn(message, cities)
    model = None
    if request["allow_model"]:
        model = trace.call("deepseek.interpret_travel_turn", lambda: model_turn(message, context))
    if model:
        inferred = model.model_dump(mode="json", exclude_none=True)
        # A model-suggested pace or rest buffer guides the schedule. Only an
        # explicit count from the user's message becomes a hard constraint.
        inferred.pop("stops_per_day", None)
        fields = {**inferred, **fields}
    if re.search(r"(?:不限制|不限|不用限制|取消).{0,8}(?:景点|站数)|(?:景点数|站数).{0,6}(?:不限|自动|灵活)", message):
        fields["stops_per_day"] = None
    city = fields.pop("city_name", None)
    if city:
        code = next((c for c, name in cities.items() if name.removesuffix("市") == city.removesuffix("市")), None)
        if not code:
            raise AppError("TRAVEL_CITY_UNAVAILABLE", "这座城市不在当前可选范围，请用城市下拉框选择。", status_code=422)
        if code != request["city_adcode"]:
            request.update(candidates=[], selected_pois=[], interests=[], must_visit=[], avoid_places=[])
            if request.get("previous_run_id"):
                request.pop("guide_references", None)
        fields.update(city_adcode=code, city_name=cities[code])
    for key in ("interests", "must_visit", "avoid_places"):
        if key in fields:
            fields[key] = [word for word in fields[key] if 0 < len(word.strip()) <= 80]
    if request.get("previous_run_id") and not fields:
        raise AppError("TRAVEL_CHANGE_UNCLEAR", "可以告诉我每天想逛几个、几点开始或结束、交通方式，或要去掉哪个地点。", status_code=422)
    request.update(fields)
    if request["daily_start"] >= request["daily_end"]:
        raise AppError("TRAVEL_TIME_CONFLICT", "每天结束时间需要晚于出发时间。", status_code=422)
    source = "deepseek" if model else "local_rules"
    trace.add("intent", "travel_turn", "succeeded", "已把本轮要求转换为旅行条件。",
              details={"source": source, "changes": fields})
    return source


def city_guide(adcode: str) -> dict | None:
    entry = CITY_GUIDES.get(adcode)
    if not entry:
        return None
    name, topics, note = entry
    return {"title": f"{name}旅行指南", "note": note, "topics": topics,
            "source": "Voyaura 本地城市知识库", "reference_url": "https://china.omuat.com/zh/cities/"}
