import copy
import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.guide_stays import apply_stay_guides
from app.agent.models import AgentRun, SavedArtifact
from app.agent.planner import (
    assemble_days,
    flexible_sightseeing,
    groups_for_plan,
    validate_plan,
)
from app.agent.schemas import ConfirmRequest, DraftEdit, RunCreate, RunOut
from app.agent.tools import (
    SUPPORT_FACILITY,
    AgentSettings,
    ToolTrace,
    collect_candidates,
    collect_legs,
    local_intent,
    match_attraction,
    model_intent,
)
from app.agent.travel_chat import CITY_GUIDES, city_guide, resolve_turn
from app.errors import AppError
from app.integrations.amap import AMapClient
from app.models import City, CityMemory, MediaAsset, User

logger = logging.getLogger("voyaura.agent")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def run_content_digest(run: AgentRun) -> str:
    return digest(
        {
            "user": str(run.user_id),
            "run": str(run.id),
            "revision": run.revision,
            "title": run.title,
            "result": run.result_snapshot,
            "input": run.input_hash,
        }
    )


def get_run(db: Session, actor: User, run_id: uuid.UUID) -> AgentRun:
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == actor.id))
    if run is None:
        raise AppError("AGENT_RUN_NOT_FOUND", "任务不存在或不属于当前用户。", status_code=404)
    recover_run(db, run)
    return run


def media_fingerprint(db: Session, memory_id: uuid.UUID) -> str:
    assets = db.scalars(
        select(MediaAsset)
        .where(
            MediaAsset.memory_id == memory_id,
            MediaAsset.upload_status == "ready",
            MediaAsset.scan_status == "clean",
        )
        .order_by(MediaAsset.id)
    ).all()
    return digest([(str(a.id), a.kind, a.byte_size) for a in assets])


def story_sources_current(db: Session, run: AgentRun) -> bool:
    for source in run.result_snapshot.get("source_memories", []):
        memory = db.scalar(
            select(CityMemory).where(
                CityMemory.id == uuid.UUID(source["id"]),
                CityMemory.user_id == run.user_id,
            )
        )
        if memory is None or utc(memory.updated_at).isoformat() != source["source_updated_at"]:
            return False
        if media_fingerprint(db, memory.id) != source.get("media_fingerprint"):
            return False
    return True


def recover_run(db: Session, run: AgentRun) -> None:
    """A bounded lease terminates abandoned work without silently repeating paid tools."""
    cutoff = datetime.now(UTC) - timedelta(seconds=AgentSettings().run_timeout_seconds)
    if run.status == "running" and utc(run.updated_at) < cutoff:
        result = {
            "intent_source": "local_rules",
            "verification_status": "information_missing",
            "summary": "任务执行租约已到期，可能因服务中断而未完成。请新建任务重试。",
            "warnings": ["不自动重复调用外部服务，避免重复消耗额度。"],
            "unknowns": ["中断前的工具执行结果未知。"],
            "recovery_code": "AGENT_RUN_INTERRUPTED",
        }
        event = {
            "sequence": len(run.events) + 1,
            "at": datetime.now(UTC).isoformat(),
            "stage": "recovery",
            "tool": "execution_lease",
            "status": "failed",
            "message": "识别到中断或超时任务；禁止伪造成功及自动重复收费。",
            "attempt": 1,
        }
        changed = db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run.id,
                AgentRun.status == "running",
                AgentRun.updated_at < cutoff,
            )
            .values(
                status="failed",
                result_snapshot=result,
                events=run.events + [event],
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount:
            db.commit()
        else:
            db.rollback()
        db.refresh(run)
    if (
        run.kind == "story"
        and run.status == "awaiting_confirmation"
        and run.result_snapshot.get("source_memories")
        and not story_sources_current(db, run)
    ):
        # Withdraw unsaved source text, including an edited draft based on those sources.
        result = {
            "intent_source": "local_rules",
            "verification_status": "information_missing",
            "summary": "来源记忆或媒体已变化，旧故事草案已撤回，请重新整理。",
            "warnings": ["未确认草案不保留已撤回来源正文。"],
            "unknowns": ["需重新授权读取当前来源。"],
            "source_memories": [],
            "story_body": "",
            "recovery_code": "STORY_SOURCES_CHANGED",
        }
        changed = db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run.id,
                AgentRun.status == "awaiting_confirmation",
                AgentRun.revision == run.revision,
            )
            .values(
                status="needs_input",
                revision=run.revision + 1,
                result_snapshot=result,
                confirmation_hash=None,
                content_digest=None,
                confirmation_expires_at=None,
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount:
            db.commit()
        else:
            db.rollback()
        db.refresh(run)


def out(db: Session, run: AgentRun) -> RunOut:
    saved = db.scalar(select(SavedArtifact.id).where(SavedArtifact.run_id == run.id))
    return RunOut(
        id=run.id,
        kind=run.kind,
        status=run.status,
        revision=run.revision,
        title=run.title,
        request=run.request_snapshot,
        result=run.result_snapshot,
        events=run.events,
        created_at=run.created_at,
        updated_at=run.updated_at,
        saved_artifact_id=saved,
    )


def build_plan(request: dict, candidates: list[dict], evidence_legs: list[dict]) -> dict:
    excluded = request.get("excluded_candidate_ids", [])
    active = [
        c for c in candidates if c["id"] not in excluded
        and (c["source"] != "amap" or not SUPPORT_FACILITY.search(c["name"]))
    ]
    active, unmatched_guides = apply_stay_guides(request, active)
    groups = groups_for_plan(request, active)
    days = assemble_days(request, groups, evidence_legs)
    validation = validate_plan(request, active, days)
    warnings = ["本版为城市日间活动草案；不包含机票、酒店、餐饮、预约与返程，不提供全局最优保证。"]
    if any(c["stay_source"] == "planning_assumption" for c in active):
        warnings.append("缺少攻略的景点按类别与旅行节奏估算停留时长。")
    if unmatched_guides:
        warnings.append("攻略未匹配到唯一景点，请核对日程内的正式名称：" + "、".join(unmatched_guides))
    if validation["unplaced_candidates"]:
        warnings.append("为保留旅行节奏，未安排：" + "、".join(validation["unplaced_candidates"]))
    for required in request["must_visit"]:
        matches = match_attraction(required, active)
        passed = len(matches) == 1 and any(
            s["candidate_id"] == matches[0]["id"] for d in days for s in d["stops"]
        )
        validation["checks"].append(
            {
                "code": "required_place_match",
                "status": "pass" if passed else "fail",
                "message": f"必去地点“{required}”须唯一匹配且已安排；当前匹配{len(matches)}个。",
            }
        )
        if not passed and active:
            validation["verification_status"] = "conflict"
    visited_ids = {stop["candidate_id"] for day in days for stop in day["stops"]}
    for poi in request.get("selected_pois", []):
        if f"amap:{poi['id']}" not in visited_ids:
            validation["checks"].append(
                {
                    "code": "selected_poi_unavailable",
                    "status": "fail",
                    "message": f"未能核实或安排已选地点“{poi['name']}”，请重查地点或调整游玩时间。",
                }
            )
            if active:
                validation["verification_status"] = "conflict"
    status = validation.pop("verification_status")
    unknowns = validation.pop("unknowns")
    return {
        "intent_source": "local_rules",
        "verification_status": status,
        "summary": (
            f"已生成{request['days']}天城市活动草案，待核实开放、费用及完整交通条件。"
            if active
            else "本次没有查到可用地点。可以搜索具体地名，或先试用离线演练。"
        ),
        "warnings": warnings,
        "unknowns": unknowns,
        "candidates": candidates,
        "days": days,
        "validation": validation,
        "constraints": {
            k: request[k]
            for k in (
                "days",
                "daily_start",
                "daily_end",
                "budget_yuan",
                "transport",
                "pace",
                "must_visit",
            )
        } | {
            "stops_per_day": request.get("stops_per_day"),
            "adaptive": flexible_sightseeing(request),
        },
        "evidence_legs": evidence_legs,
    }


def describe_chat_plan(result: dict, request: dict) -> str:
    stops = [(day["day"], stop) for day in result["days"] for stop in day["stops"]]
    required = request["must_visit"]
    if required:
        details = []
        scheduled = [stop for _, stop in stops]
        for name in required:
            matches = match_attraction(name, scheduled)
            match = next(((day, stop) for day, stop in stops if stop in matches), None) if len(matches) == 1 else None
            if match:
                day, stop = match
                details.append(f"把{stop['name']}放到第 {day} 天 {stop['arrival']} 了。")
                if "大学" in name and ("校园" in name or "校区" in name):
                    details.append("访客开放和预约记得在出发前看一下学校通知。")
            else:
                details.append(f"这次还没能把{name}排进去。可以先核对地点名称，再试一个宽松点的时段。")
        if result["verification_status"] == "conflict":
            details.append("草案里还有条件需要确认，先看看安排再决定。")
        return "".join(details)
    if not stops:
        return "这次还没有查到能排进路线的地点。你愿意换一个主题，还是先挑一个一定想去的地方？"
    per_day = "、".join(str(len(day["stops"])) for day in result["days"])
    if limit := request.get("stops_per_day"):
        return f"我按每天最多 {limit} 站重新排了，各天是 {per_day} 站，你看节奏合不合适。"
    return f"我试着把近一点的地方放在同一天，各天排了 {per_day} 站。每天 {request['daily_end']} 前收尾，你想再松一点也可以。"


def build_story(db: Session, actor: User, request: dict, trace: ToolTrace) -> dict:
    # User-recorded events are not attestation that the physical visit occurred.
    start = datetime.combine(
        datetime.fromisoformat(request["start_date"]).date(), time.min, tzinfo=UTC
    ) - timedelta(hours=8)
    end = start + timedelta(days=request["days"])
    query = (
        select(CityMemory, City)
        .join(City, City.id == CityMemory.city_id)
        .where(
            CityMemory.user_id == actor.id,
            City.adcode == request["city_adcode"],
            CityMemory.occurred_at >= start,
            CityMemory.occurred_at < end,
        )
        .order_by(CityMemory.occurred_at, CityMemory.id)
    )
    if request["memory_ids"]:
        selected = [uuid.UUID(x) for x in request["memory_ids"]]
        query = query.where(CityMemory.id.in_(selected))
        own_ids = set(
            db.scalars(
                select(CityMemory.id).where(
                    CityMemory.id.in_(selected), CityMemory.user_id == actor.id
                )
            )
        )
        if own_ids != set(selected):
            raise AppError(
                "STORY_SOURCE_NOT_FOUND", "所选记忆不存在或不属于当前用户。", status_code=404
            )
    rows = db.execute(query.limit(40)).all()
    sources = []
    for memory, city in rows:
        assets = db.scalars(
            select(MediaAsset).where(
                MediaAsset.memory_id == memory.id,
                MediaAsset.upload_status == "ready",
                MediaAsset.scan_status == "clean",
            )
        ).all()
        date_local = (utc(memory.occurred_at) + timedelta(hours=8)).date().isoformat()
        sources.append(
            {
                "id": str(memory.id),
                "title": memory.title,
                "body": (memory.body or "")[:1800],
                "date": date_local,
                "city": city.name_zh,
                "photo_count": sum(a.kind == "photo" for a in assets),
                "vlog_count": sum(a.kind == "vlog" for a in assets),
                "provenance": "user_recorded",
                "source_updated_at": utc(memory.updated_at).isoformat(),
                "media_fingerprint": media_fingerprint(db, memory.id),
            }
        )
    trace.add(
        "tool",
        "memory.read_authorized",
        "succeeded",
        "只读取当前用户授权的城市与日期范围。",
        details={"memory_count": len(sources), "sent_externally": False},
    )
    body = "\n\n".join(
        f"{m['date']} · {m['city']}\n{m['title']}\n{m['body']}"
        f"\n记录中有{m['photo_count']}张可用照片、{m['vlog_count']}段Vlog。"
        for m in sources
    )[:16000]
    return {
        "intent_source": "local_rules",
        "verification_status": "conditional" if sources else "information_missing",
        "summary": f"按日期整理了{len(sources)}条用户记录，正文可编辑；未生成虚构经历。",
        "warnings": [
            "本草案整理用户自己记录的文字与媒体数量；不等于物理到访证明，不进行照片内容识别。"
        ],
        "unknowns": [] if sources else ["所选城市和日期范围内没有可用旅行记录。"],
        "source_memories": sources,
        "story_body": body,
    }


def create_run(db: Session, actor: User, payload: RunCreate, client: AMapClient) -> AgentRun:
    request = payload.model_dump(mode="json")
    for optional in ("selected_pois", "chat_message", "previous_run_id"):
        if not request[optional]:
            del request[optional]
    if request["guide_references"] is None:
        del request["guide_references"]
    input_hash = digest(request)
    existing = db.scalar(
        select(AgentRun).where(
            AgentRun.user_id == actor.id,
            AgentRun.client_request_id == payload.client_request_id,
        )
    )
    if existing:
        if existing.input_hash != input_hash:
            raise AppError(
                "IDEMPOTENCY_CONFLICT", "同一请求编号不能用于不同参数。", status_code=409
            )
        recover_run(db, existing)
        return existing
    previous = get_run(db, actor, payload.previous_run_id) if payload.previous_run_id else None
    if previous and (previous.kind != "plan" or previous.status not in ("awaiting_confirmation", "confirmed", "needs_input")):
        raise AppError("TRAVEL_CHAT_DRAFT_UNAVAILABLE", "当前任务还不能继续调整。", status_code=409)
    run = AgentRun(
        user_id=actor.id,
        client_request_id=payload.client_request_id,
        input_hash=input_hash,
        kind=payload.kind,
        title=f"{payload.city_name} · {'旅行计划' if payload.kind == 'plan' else '旅行故事'}",
        request_snapshot=request,
        result_snapshot={},
        events=[],
        status="running",
        revision=1,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AgentRun).where(
                AgentRun.user_id == actor.id,
                AgentRun.client_request_id == payload.client_request_id,
            )
        )
        if existing and existing.input_hash == input_hash:
            recover_run(db, existing)
            return existing
        raise AppError("IDEMPOTENCY_CONFLICT", "请求编号发生并发冲突。", status_code=409) from None
    trace = ToolTrace()
    trace.add("planning", "workflow", "running", "已建立持久化任务；先核对授权，再调用白名单工具。")
    try:
        if payload.kind == "story":
            result = build_story(db, actor, request, trace)
        else:
            intent_source = "local_rules"
            knowledge = None
            if payload.chat_message:
                if previous:
                    fields = (
                        "city_adcode", "city_name", "start_date", "days", "daily_start", "daily_end",
                        "budget_yuan", "transport", "pace", "interests", "must_visit",
                        "candidates", "stops_per_day", "rest_minutes", "avoid_places",
                    )
                    request.update({key: previous.request_snapshot[key] for key in fields
                                    if key in previous.request_snapshot})
                    if payload.allow_external and previous.request_snapshot.get("selected_pois"):
                        request["selected_pois"] = previous.request_snapshot["selected_pois"]
                    if "guide_references" not in request and request["city_adcode"] == previous.request_snapshot.get("city_adcode"):
                        request["guide_references"] = previous.request_snapshot.get("guide_references", [])
                cities = {key: data[0] for key, data in CITY_GUIDES.items()}
                cities.update({code: name for code, name in db.execute(select(City.adcode, City.name_zh))})
                intent_source = resolve_turn(request, cities, trace)
                avoided = request.get("avoid_places", [])
                for key in ("must_visit", "selected_pois", "candidates"):
                    request[key] = [
                        value for value in request.get(key, [])
                        if not any(word in (value if isinstance(value, str) else value["name"]) for word in avoided)
                    ]
            knowledge = city_guide(request["city_adcode"]) if payload.allow_external or payload.chat_message else None
            if knowledge:
                trace.add("knowledge", "city_guide.lookup", "succeeded", "已读取本地城市指南。")
            topics = local_intent(request)
            if knowledge and topics == ["风景名胜"]:
                topics = [*topics, *knowledge["topics"][:2]]
            trace.add(
                "intent",
                "local_rules",
                "succeeded",
                "使用有限关键词规则，显式表单约束优先。",
                details={"topics": topics},
            )
            if payload.allow_model and not payload.chat_message:
                generated = model_intent(request, trace, AgentSettings())
                if generated is not None:
                    topics = list(dict.fromkeys(request["must_visit"] + generated))[:3]
                    intent_source = "deepseek"
            candidates = collect_candidates(request, client, trace, topics)
            scheduled, unmatched = apply_stay_guides(request, candidates)
            if request.get("guide_references"):
                trace.add(
                    "evidence", "guide_stay.apply", "succeeded", "已把匹配的攻略时长纳入排程。",
                    details={"matched_places": sum(c["stay_source"] == "guide_reference" for c in scheduled),
                             "unmatched_places": unmatched},
                )
            groups = groups_for_plan(request, scheduled)
            legs = collect_legs(request, groups, client, trace)
            trace.add(
                "optimization",
                "day_planner",
                "succeeded",
                "完成按天空间分组与日内近邻排序；未宣称最优解。",
            )
            result = build_plan(request, candidates, legs)
            result["intent_source"] = intent_source
            if payload.chat_message:
                earlier = previous.result_snapshot.get("chat", []) if previous else []
                reply = describe_chat_plan(result, request)
                result["chat"] = [*earlier[-10:], {"role": "user", "text": payload.chat_message},
                                  {"role": "assistant", "text": reply}]
                result["city_guide"] = knowledge
            trace.add(
                "validation",
                "independent_validator",
                result["verification_status"],
                "依据最终时间线独立检查必去地点、时间、开放窗口和费用下界。",
            )
        status = (
            "needs_input"
            if result["verification_status"] == "information_missing"
            else "awaiting_confirmation"
        )
    except AppError:
        # Preserve failure evidence without turning permission/provider errors into success.
        db.rollback()
        run = db.get(AgentRun, run.id)
        trace.add("workflow", "workflow", "failed", "任务因权限或数据条件未完成。")
        run.status = "failed"
        run.events = trace.events
        run.updated_at = datetime.now(UTC)
        db.commit()
        raise
    except Exception:
        logger.exception("agent_execution_failed run_id=%s", run.id)
        db.rollback()
        run = db.get(AgentRun, run.id)
        trace.add("workflow", "workflow", "failed", "执行发生异常，未生成成功结果。")
        result = {
            "verification_status": "information_missing",
            "intent_source": "local_rules",
            "summary": "任务失败，可查看调用记录并新建任务重试。",
            "warnings": [],
            "unknowns": ["任务执行未完成。"],
        }
        status = "failed"
    trace.add("workflow", "workflow", status, "草案与证据已保存，尚未写入正式旅行档案。")
    changed = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run.id,
            AgentRun.user_id == actor.id,
            AgentRun.status == "running",
        )
        .values(
            request_snapshot=request,
            title=f"{request['city_name']} · 旅行计划" if payload.chat_message else run.title,
            result_snapshot=result, events=trace.events, status=status, updated_at=datetime.now(UTC)
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount:
        db.commit()
    else:
        db.rollback()  # A recovered/expired run cannot be overwritten by a late executor.
    db.refresh(run)
    return run


def edit_run(db: Session, actor: User, run_id: uuid.UUID, edit: DraftEdit) -> AgentRun:
    run = get_run(db, actor, run_id)
    if run.status not in ("awaiting_confirmation", "needs_input"):
        raise AppError(
            "AGENT_RUN_NOT_EDITABLE",
            "当前状态不能编辑；已保存的档案保持不可变快照。",
            status_code=409,
        )
    if run.revision != edit.expected_revision:
        raise AppError("AGENT_REVISION_CONFLICT", "草稿已被修改，请刷新。", status_code=409)
    request, result = copy.deepcopy(run.request_snapshot), copy.deepcopy(run.result_snapshot)
    if run.kind == "story":
        if edit.excluded_candidate_ids is not None or edit.daily_end is not None or edit.guide_references is not None:
            raise AppError("AGENT_WRONG_EDIT_KIND", "故事仅支持标题与正文编辑。", status_code=422)
        if not result.get("source_memories"):
            raise AppError(
                "STORY_NO_SOURCES",
                "没有来源记录时不能把输入正文包装为已整理故事。",
                status_code=409,
            )
        if edit.story_body is not None:
            result["story_body"] = edit.story_body
            result["edited_by_user"] = True
    else:
        if edit.story_body is not None:
            raise AppError("AGENT_WRONG_EDIT_KIND", "行程不接收故事正文。", status_code=422)
        if edit.excluded_candidate_ids is not None:
            valid_ids = {c["id"] for c in result.get("candidates", [])}
            if not set(edit.excluded_candidate_ids).issubset(valid_ids):
                raise AppError("AGENT_CANDIDATE_NOT_FOUND", "排除列表含未知候选。", status_code=422)
            request["excluded_candidate_ids"] = edit.excluded_candidate_ids
        if edit.daily_end is not None:
            if edit.daily_end <= request["daily_start"]:
                raise AppError(
                    "AGENT_INVALID_WINDOW", "结束时间必须晚于开始时间。", status_code=422
                )
            request["daily_end"] = edit.daily_end
        if edit.guide_references is not None:
            request["guide_references"] = [ref.model_dump(mode="json") for ref in edit.guide_references]
        result = build_plan(request, result.get("candidates", []), result.get("evidence_legs", []))
        result["intent_source"] = run.result_snapshot.get("intent_source", "local_rules")
        for key in ("chat", "city_guide"):
            if key in run.result_snapshot:
                result[key] = run.result_snapshot[key]
    title = edit.title if edit.title is not None else run.title
    new_status = (
        "needs_input"
        if result["verification_status"] == "information_missing"
        else "awaiting_confirmation"
    )
    events = run.events + [
        {
            "sequence": len(run.events) + 1,
            "at": datetime.now(UTC).isoformat(),
            "stage": "revision",
            "tool": "draft.edit",
            "status": "succeeded",
            "message": "已按攻略建议重排行程，旧确认已失效。" if edit.guide_references is not None
            else "用户修改草案，旧确认已失效。",
            "attempt": 1,
        }
    ]
    count = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run.id,
            AgentRun.user_id == actor.id,
            AgentRun.revision == edit.expected_revision,
            AgentRun.status.in_(("awaiting_confirmation", "needs_input")),
        )
        .values(
            title=title,
            request_snapshot=request,
            result_snapshot=result,
            status=new_status,
            revision=edit.expected_revision + 1,
            events=events,
            confirmation_hash=None,
            confirmation_expires_at=None,
            content_digest=None,
            updated_at=datetime.now(UTC),
        )
    )
    if count.rowcount != 1:
        db.rollback()
        raise AppError("AGENT_REVISION_CONFLICT", "草稿被并发修改，请刷新。", status_code=409)
    db.commit()
    db.refresh(run)
    return run


def prepare_confirmation(db: Session, actor: User, run: AgentRun, revision: int) -> dict:
    if run.status != "awaiting_confirmation" or run.revision != revision:
        raise AppError(
            "AGENT_CONFIRMATION_NOT_READY", "任务状态或版本已变化，请刷新。", status_code=409
        )
    if run.result_snapshot["verification_status"] in ("conflict", "information_missing"):
        raise AppError(
            "AGENT_CONSTRAINTS_UNRESOLVED", "请先解决约束冲突或补充资料。", status_code=409
        )
    token = secrets.token_urlsafe(36)
    expires = datetime.now(UTC) + timedelta(seconds=AgentSettings().confirmation_ttl_seconds)
    content_digest = run_content_digest(run)
    changed = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run.id,
            AgentRun.user_id == actor.id,
            AgentRun.revision == revision,
            AgentRun.status == "awaiting_confirmation",
        )
        .values(
            confirmation_hash=hashlib.sha256(token.encode()).hexdigest(),
            content_digest=content_digest,
            confirmation_expires_at=expires,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise AppError("AGENT_REVISION_CONFLICT", "草稿已变化。", status_code=409)
    db.commit()
    return {
        "confirmation_token": token,
        "content_digest": content_digest,
        "expires_at": expires,
        "revision": revision,
        "summary": f"将“{run.title}”保存为当前用户私有{'行程' if run.kind == 'plan' else '故事'}。不创建到访、不公开发布。",
        "requires_unverified_acknowledgement": run.result_snapshot["verification_status"]
        != "validated",
    }


def confirm_run(db: Session, actor: User, run: AgentRun, payload: ConfirmRequest) -> AgentRun:
    if run.result_snapshot.get("recovery_code") == "STORY_SOURCES_CHANGED":
        raise AppError(
            "STORY_SOURCES_CHANGED", "来源记忆或媒体已变化，请重新整理。", status_code=409
        )
    supplied_hash = hashlib.sha256(payload.confirmation_token.encode()).hexdigest()
    if (
        run.revision != payload.expected_revision
        or not run.confirmation_hash
        or not secrets.compare_digest(run.confirmation_hash, supplied_hash)
        or not run.content_digest
        or not secrets.compare_digest(run.content_digest, payload.content_digest)
        or not secrets.compare_digest(run_content_digest(run), payload.content_digest)
    ):
        raise AppError(
            "AGENT_CONFIRMATION_MISMATCH", "确认与当前用户、内容或版本不匹配。", status_code=409
        )
    if run.status == "confirmed":
        return run
    if (
        run.status != "awaiting_confirmation"
        or run.confirmation_expires_at is None
        or utc(run.confirmation_expires_at) < datetime.now(UTC)
    ):
        raise AppError(
            "AGENT_CONFIRMATION_EXPIRED", "确认已过期或状态变化，请重新预览。", status_code=409
        )
    if (
        run.result_snapshot["verification_status"] != "validated"
        and not payload.acknowledge_unverified
    ):
        raise AppError(
            "AGENT_UNVERIFIED_ACK_REQUIRED", "保存前请确认已知悉未核实条件。", status_code=422
        )
    # A source deletion/change between preview and save must not resurrect old private content.
    if run.kind == "story" and not story_sources_current(db, run):
        raise AppError(
            "STORY_SOURCES_CHANGED", "来源记忆或媒体已变化，请重新整理。", status_code=409
        )
    count = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run.id,
            AgentRun.user_id == actor.id,
            AgentRun.revision == payload.expected_revision,
            AgentRun.status == "awaiting_confirmation",
            AgentRun.confirmation_hash == supplied_hash,
            AgentRun.confirmation_expires_at >= datetime.now(UTC),
        )
        .values(status="confirmed", updated_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if count.rowcount != 1:
        db.rollback()
        db.refresh(run)
        if run.status == "confirmed":
            # Re-enter the full digest/revision/token check. A newer confirmed revision
            # is not a successful replay of this request's stale confirmation.
            return confirm_run(db, actor, run, payload)
        raise AppError("AGENT_CONFIRMATION_CONFLICT", "草稿或确认已变化，请刷新。", status_code=409)
    artifact = SavedArtifact(
        user_id=actor.id,
        run_id=run.id,
        kind=run.kind,
        title=run.title,
        content=copy.deepcopy(run.result_snapshot),
        content_digest=payload.content_digest,
        acknowledgement="用户确认条件草案仍有未核实信息。"
        if payload.acknowledge_unverified
        else None,
    )
    db.add(artifact)
    db.commit()
    db.refresh(run)
    return run
