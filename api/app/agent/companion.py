"""Travel conversation, independent of itinerary mutations."""

import json
import re
import uuid
from typing import Literal

import httpx
from langchain_core.exceptions import OutputParserException
from langchain_deepseek import ChatDeepSeek
from openai import OpenAIError
from pydantic import Field, SecretStr

from app.agent.schemas import StrictModel
from app.agent.travel_chat import CITY_GUIDES, city_guide, local_turn, model_credentials
from app.config import settings
from app.errors import AppError

CAMPUSES = {
    "南": ("中山大学广州校区南校园", "海珠区"),
    "北": ("中山大学广州校区北校园", "越秀区"),
    "东": ("中山大学广州校区东校园", "番禺区"),
}
CAMPUS_SOURCE = {"label": "中山大学官网", "url": "https://www.sysu.edu.cn/"}
ATTRACTION_NOTES = {
    "广州塔": ("适合想看广州城市天际线的人。可以把它和珠江边散步安排在一起，按自己对登塔的兴趣决定停留多久。",
            "广州塔官网", "https://www.cantontower.com/"),
    "广东省博物馆": ("如果你喜欢看展，可以把它当作半天的主要安排，留一点时间慢慢看自己感兴趣的展厅。",
                "广东省博物馆官网", "https://www.gdmuseum.com/"),
}


class CompanionMessage(StrictModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=1500)


class CompanionRequest(StrictModel):
    message: str = Field(min_length=1, max_length=1500)
    city_adcode: str = Field(default="440100", pattern=r"^\d{6}$")
    plan_id: uuid.UUID | None = None
    history: list[CompanionMessage] = Field(default_factory=list, max_length=8)
    allow_model: bool = False


class CompanionReply(StrictModel):
    text: str = Field(min_length=1, max_length=800)
    planning_request: str | None = Field(default=None, min_length=2, max_length=1500)


def proposal(message: str, text: str) -> dict:
    return {"text": text, "planning_request": message}


def campus_reply(payload: CompanionRequest) -> dict | None:
    message = payload.message
    names_campus = bool(re.search(r"中山大学|(?<![\u4e00-\u9fff])中大|去中大|看中大|中大[南北东]", message))
    last_asked_campus = bool(payload.history and payload.history[-1].role == "assistant"
                             and all(x in payload.history[-1].text for x in ("南校园", "北校园", "东校园")))
    direction = re.search(r"([南北东])(?:校园|校区|校)", message)
    if last_asked_campus and not direction:
        direction = re.fullmatch(r"(?:选|去|就)?\s*([南北东])(?:吧|那个)?[。！]?", message)
    if not names_campus and not (last_asked_campus and direction):
        return None
    if direction:
        name, district = CAMPUSES[direction[1]]
        return {**proposal(f"想去{name}", f"好，那就看{district}的{name}。我可以把它设为必去地点。出发前再核对校方的访客开放和预约要求。"),
                "sources": [CAMPUS_SOURCE]}
    return {
        "text": "想去中大逛逛呀？广州有南校园、北校园和东校园。想看康乐园的话，可以选海珠区的南校园。你想去哪个？",
        "choices": [{"label": name, "message": f"我想去{name}"} for name, _ in CAMPUSES.values()],
        "sources": [CAMPUS_SOURCE],
    }


def companion_model(payload: CompanionRequest, context: dict) -> CompanionReply | None:
    key, model = model_credentials()
    if not key:
        return None
    try:
        llm = ChatDeepSeek(
            api_key=SecretStr(key), model=model, temperature=0.55, timeout=18, max_retries=0,
            base_url=settings.deepseek_base_url,
        ).with_structured_output(CompanionReply, method="function_calling")
        response = llm.invoke([
            ("system", (
                "你是小曦，一位会倾听的旅行伙伴。用自然简短的中文回应本轮实际说的话。"
                "用户表达开心、疲惫、紧张或独自旅行的感受时，先接住已经表达的情绪，再顺着聊；不要替对方下诊断。"
                "问景点时用提供的资料给实用介绍，未知的实时开放、票价、预约和路线不要猜。"
                "用户直接要求安排或调整时才提议生成草案，planning_request 写简短、忠于原意的可执行需求。"
                "如果只在聊天、问景点、表达感受或需求不清楚，planning_request 留空。"
                "不声称已经查询、改好、保存。只返回 text 和 planning_request。"
            )),
            ("human", json.dumps({
                "当前目的地与资料": context,
                "近期对话": [turn.model_dump() for turn in payload.history],
                "这条新消息": payload.message,
            }, ensure_ascii=False)),
        ])
    except (OpenAIError, OutputParserException, httpx.HTTPError, ValueError, TypeError):
        return None
    return response if isinstance(response, CompanionReply) else None


def reply_to_companion(payload: CompanionRequest, plan_context: dict) -> dict:
    message = payload.message
    if campus := campus_reply(payload):
        return {**campus, "source": "local"}
    for name, (note, label, url) in ATTRACTION_NOTES.items():
        if name in message and re.search(r"介绍|怎么样|值得|好玩|了解|什么", message):
            return {"text": f"{name}可以这样逛。{note}", "sources": [{"label": label, "url": url}], "source": "local"}
    city_code = next(
        (code for code, (name, _, _) in CITY_GUIDES.items() if name.removesuffix("市") in message),
        payload.city_adcode,
    )
    guide = city_guide(city_code)
    if payload.allow_model:
        model_reply = companion_model(payload, {"guide": guide, "plan": plan_context})
        if model_reply is not None:
            return {**model_reply.model_dump(), "source": "deepseek"}
    if re.search(r"紧张|焦虑|担心|害怕|不安|孤单", message):
        reply = {"text": "听起来你有点担心这趟旅行。我们可以先把最让你没底的那一段想清楚。是到达后怎么走，还是一个人玩的时候怕不自在？"}
    elif re.search(r"好累|太累|疲惫|累了|没精神", message):
        reply = {"text": "那就把节奏放慢一点。今天可以留一个你最想去的地方，其他的等休息好了再决定。你现在更想先坐一会儿，还是回住处歇歇？"}
    elif re.search(r"开心|期待|兴奋|太棒|好喜欢", message):
        reply = {"text": "听得出来你很期待这趟旅行。有没有一个画面，是你最想亲眼看看或者拍下来的？"}
    elif re.search(r"一个人|独自", message):
        reply = {"text": "一个人旅行可以按自己的节奏来。你更想有一段安静的散步时间，还是想找热闹一点的地方逛？"}
    elif guide and re.search(r"介绍|有什么|推荐|去哪儿玩|去哪玩|怎么玩", message):
        reply = {"text": f"{guide['note']} 你可以先看看{'、'.join(guide['topics'])}。想先听哪个？",
                 "sources": [{"label": "城市指南索引", "url": guide["reference_url"]}]}
    elif re.search(r"谢谢|谢啦|你好|早上好|晚上好|晚安", message):
        reply = {"text": "我在呀。这趟旅行想到哪里了？可以先从一个想去的地方聊起。"}
    else:
        try:
            filters = local_turn(message, {code: value[0] for code, value in CITY_GUIDES.items()})
        except AppError as exc:
            return {"text": exc.message, "source": "local"}
        asks_to_plan = bool(re.search(r"规划|安排行程|帮我排|安排|想(?:去|看)|想来|加上|改成|换成", message))
        direct_constraints = any(key in filters for key in ("days", "daily_start", "daily_end", "stops_per_day"))
        if direct_constraints or (asks_to_plan and (filters or re.search(r"规划|安排|帮我排", message))):
            reply = proposal(message, "这个想法可以带进路线里。你准备好了，我们就按你刚说的条件试排一份。")
        else:
            reply = {"text": "可以，我们慢慢聊。你更想了解目的地，还是想说说这趟旅行让你在意的事？"}
    if "planning_request" not in reply and re.search(r"帮我排|给我安排行程", message):
        reply["planning_request"] = message
    return {**reply, "source": "local"}
