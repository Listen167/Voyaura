"""Real workflow/database tests. Explicit provider stubs are not online AMap evidence."""

import copy
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.agent.guide_stays import parse_visit_duration
from app.agent.models import AgentRun, SavedArtifact
from app.config import settings
from app.database import Base, get_db
from app.errors import AppError
from app.integrations.amap import AMapClient, AMapPoi, AMapRouteOption, get_amap_client
from app.main import app
from app.models import City, CityMemory, CityVisit, MediaAsset, User

TOKEN = "test-agent-token-not-a-real-secret-0123456789"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


class ExplicitMapStub(AMapClient):
    """Always injected, never installed as a production/default provider."""

    def __init__(self):
        super().__init__(key="")
        self.calls = 0
        self.retry_once = False
        self.invalid_duration = False
        self.invalid_coordinate = False

    def search_pois(self, **kwargs):
        self.calls += 1
        if self.retry_once and self.calls == 1:
            raise AppError("AMAP_RATE_LIMIT", "测试限流", retryable=True)
        items = [
            AMapPoi(
                id=f"TEST{i}",
                name=f"测试地点{i}",
                category="测试",
                typecode="110000",
                address="仅用于测试",
                province="广东省",
                city="广州市",
                district="天河区",
                adcode="440106",
                longitude=(float("nan") if self.invalid_coordinate else 113.3 + i * 0.001),
                latitude=23.1 + i * 0.001,
                opening_hours="09:00-18:00",
            )
            for i in range(4)
        ]
        return items, len(items)

    def plan_route(self, **kwargs):
        self.calls += 1
        return [
            AMapRouteOption(
                distance_meters=2000, duration_seconds=0 if self.invalid_duration else 600, steps=()
            )
        ], None

    def get_poi_detail(self, poi_id):
        items, _ = self.search_pois()
        return next(poi for poi in items if poi.id == poi_id)


@dataclass
class Context:
    client: TestClient
    sessions: sessionmaker
    provider: ExplicitMapStub
    owner_id: uuid.UUID
    other_id: uuid.UUID
    city_id: uuid.UUID


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Context, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'agent-tests.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        owner = User(username="AuroraRovella", display_name="测试所有者")
        other = User(username="OtherTraveler", display_name="隔离用户")
        city = City(
            adcode="440100",
            name_zh="广州市",
            name_en="Guangzhou",
            province_zh="广东省",
            longitude=113.26,
            latitude=23.12,
        )
        db.add_all([owner, other, city])
        db.flush()
        owner_id, other_id, city_id = owner.id, other.id, city.id

    def database():
        with sessions() as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = database
    provider = ExplicitMapStub()
    app.dependency_overrides[get_amap_client] = lambda: provider
    monkeypatch.setattr(settings, "auth_token", TOKEN)
    monkeypatch.setattr(settings, "auth_username", "AuroraRovella")
    monkeypatch.setenv("VOYAURA_AGENT_LLM_ENABLED", "false")
    try:
        with TestClient(app, headers=HEADERS) as client:
            yield Context(client, sessions, provider, owner_id, other_id, city_id)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def plan_payload(**updates):
    value = {
        "client_request_id": str(uuid.uuid4()),
        "kind": "plan",
        "goal": "两天轻松旅行",
        "city_adcode": "440100",
        "city_name": "广州市",
        "start_date": "2026-12-01",
        "days": 2,
        "daily_start": "09:00",
        "daily_end": "18:00",
        "budget_yuan": 300,
        "candidates": [
            {
                "name": f"用户提供地点{i}",
                "longitude": 113.3 + 0.003 * i,
                "latitude": 23.1 + 0.002 * i,
                "stay_minutes": 60,
                "opening_start": "09:00",
                "opening_end": "18:00",
                "cost_yuan": 10,
            }
            for i in range(4)
        ],
    }
    value.update(updates)
    return value


def create(ctx: Context, **updates):
    response = ctx.client.post("/api/v1/agent/runs", json=plan_payload(**updates))
    assert response.status_code == 201, response.text
    return response.json()


def confirmation(ctx: Context, run: dict):
    response = ctx.client.post(
        f"/api/v1/agent/runs/{run['id']}/confirmation", json={"expected_revision": run["revision"]}
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    return {
        "expected_revision": run["revision"],
        "confirmation_token": preview["confirmation_token"],
        "content_digest": preview["content_digest"],
        "acknowledge_unverified": True,
    }


def test_local_workflow_persists_real_computation_and_idempotent_save(ctx):
    payload = plan_payload()
    first = ctx.client.post("/api/v1/agent/runs", json=payload).json()
    repeated = ctx.client.post("/api/v1/agent/runs", json=payload).json()
    assert first["id"] == repeated["id"]
    assert first["result"]["verification_status"] == "conditional"
    assert first["result"]["intent_source"] == "local_rules"
    assert len(first["result"]["days"]) == 2
    assert all(c["source"] == "user_provided" for c in first["result"]["candidates"])
    assert any("交通时间未知" in u for u in first["result"]["unknowns"])
    assert ctx.provider.calls == 0
    assert len(first["events"]) >= 5
    assert TOKEN not in str(first)
    body = confirmation(ctx, first)
    path = f"/api/v1/agent/runs/{first['id']}/confirm"
    saved = ctx.client.post(path, json=body)
    again = ctx.client.post(path, json=body)
    assert saved.status_code == again.status_code == 200
    assert saved.json()["status"] == "confirmed"
    assert saved.json()["saved_artifact_id"] == again.json()["saved_artifact_id"]
    with ctx.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SavedArtifact)) == 1
        assert db.scalar(select(func.count()).select_from(CityVisit)) == 0
    assert ctx.client.get(f"/api/v1/agent/runs/{first['id']}").json()["status"] == "confirmed"
    assert ctx.client.get("/api/v1/agent/runs").json()["items"][0]["id"] == first["id"]


def test_empty_provider_stays_needs_input_and_cannot_save(ctx):
    run = create(ctx, candidates=[], allow_external=True, interests=["博物馆"])
    assert run["status"] == "needs_input"
    assert run["result"]["verification_status"] == "information_missing"
    assert any(e.get("details", {}).get("code") == "AMAP_KEY_MISSING" for e in run["events"])
    assert (
        ctx.client.post(
            f"/api/v1/agent/runs/{run['id']}/confirmation", json={"expected_revision": 1}
        ).status_code
        == 409
    )


def test_hard_constraints_are_independently_rejected(ctx):
    run = create(ctx, budget_yuan=1, daily_end="09:30")
    assert run["result"]["verification_status"] == "conflict"
    failed = {x["code"] for x in run["result"]["validation"]["checks"] if x["status"] == "fail"}
    assert {"budget_lower_bound", "daily_end"} <= failed
    assert (
        ctx.client.post(
            f"/api/v1/agent/runs/{run['id']}/confirmation", json={"expected_revision": 1}
        ).status_code
        == 409
    )


def test_edits_invalidate_confirmation_and_can_repair_time_conflict(ctx):
    run = create(ctx, daily_end="09:30")
    path = f"/api/v1/agent/runs/{run['id']}"
    repaired = ctx.client.patch(
        path + "/draft", json={"expected_revision": 1, "daily_end": "18:00"}
    )
    assert repaired.status_code == 200
    assert repaired.json()["revision"] == 2
    old = confirmation(ctx, repaired.json())
    edited = ctx.client.patch(path + "/draft", json={"expected_revision": 2, "title": "已编辑计划"})
    assert edited.status_code == 200
    assert ctx.client.post(path + "/confirm", json=old).status_code == 409
    assert (
        ctx.client.patch(
            path + "/draft", json={"expected_revision": 2, "title": "覆盖"}
        ).status_code
        == 409
    )


def test_confirm_requires_content_token_expiry_and_unknown_ack(ctx):
    run = create(ctx)
    body = confirmation(ctx, run)
    path = f"/api/v1/agent/runs/{run['id']}/confirm"
    no_ack = {**body, "acknowledge_unverified": False}
    assert ctx.client.post(path, json=no_ack).status_code == 422
    assert ctx.client.post(path, json={**body, "content_digest": "0" * 64}).status_code == 409
    assert (
        ctx.client.post(path, json={**body, "confirmation_token": "invalid" * 8}).status_code == 409
    )
    with ctx.sessions.begin() as db:
        row = db.get(AgentRun, uuid.UUID(run["id"]))
        row.confirmation_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert ctx.client.post(path, json=body).status_code == 409


def test_identity_isolation_and_request_parameter_conflict(ctx, monkeypatch):
    run = create(ctx)
    monkeypatch.setattr(settings, "auth_username", "OtherTraveler")
    assert ctx.client.get(f"/api/v1/agent/runs/{run['id']}").status_code == 404
    assert ctx.client.get("/api/v1/agent/runs").json()["items"] == []
    assert (
        ctx.client.post(
            f"/api/v1/agent/runs/{run['id']}/confirmation", json={"expected_revision": 1}
        ).status_code
        == 404
    )
    monkeypatch.setattr(settings, "auth_username", "AuroraRovella")
    payload = plan_payload()
    assert ctx.client.post("/api/v1/agent/runs", json=payload).status_code == 201
    payload["goal"] = "修改目标"
    assert ctx.client.post("/api/v1/agent/runs", json=payload).status_code == 409


def test_concurrent_confirmation_writes_one_artifact(ctx):
    run = create(ctx)
    body = confirmation(ctx, run)
    path = f"/api/v1/agent/runs/{run['id']}/confirm"
    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: ctx.client.post(path, json=body), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert len({r.json()["saved_artifact_id"] for r in responses}) == 1
    with ctx.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SavedArtifact)) == 1


def test_explicit_map_stub_retry_success_is_traced_but_not_full_trip_validated(ctx):
    ctx.provider.key = "explicit-test-only"
    ctx.provider.retry_once = True
    run = create(ctx, candidates=[], allow_external=True, interests=["测试主题"])
    assert run["status"] == "awaiting_confirmation"
    assert all(c["source"] == "amap" for c in run["result"]["candidates"])
    assert any(e["status"] == "retrying" for e in run["events"])
    assert any(leg["source"] == "amap" for day in run["result"]["days"] for leg in day["legs"])
    assert run["result"]["verification_status"] == "conditional"
    assert run["result"]["validation"]["unknown_cost_count"] > 0


def test_map_planning_accepts_poi_selection_without_user_coordinates(ctx):
    ctx.provider.key = "explicit-test-only"
    run = create(
        ctx,
        candidates=[],
        allow_external=True,
        selected_pois=[{"id": "TEST2", "name": "客户端显示名"}],
    )
    assert run["status"] == "awaiting_confirmation"
    selected = next(c for c in run["result"]["candidates"] if c["id"] == "amap:TEST2")
    assert selected["name"] == "测试地点2"
    assert selected["verification"] == "verified"
    assert selected["must_visit"] is True
    assert any(e["tool"] == "amap.get_poi_detail" for e in run["events"])
    assert any(
        (e["details"].get("topics") or [])[:1] == ["风景名胜"]
        for e in run["events"] if "details" in e
    )
    assert any(
        s["candidate_id"] == selected["id"]
        for day in run["result"]["days"] for s in day["stops"]
    )


def test_natural_language_plan_and_followup_share_conditions_and_city_guide(ctx):
    ctx.provider.key = "explicit-test-only"
    first = create(
        ctx, candidates=[], allow_external=True,
        chat_message="广州两天，每天三个景点，坐地铁",
    )
    assert first["request"]["stops_per_day"] == 3
    assert first["request"]["transport"] == "transit"
    assert first["result"]["city_guide"]["title"] == "广州市旅行指南"
    assert first["result"]["intent_source"] == "local_rules"
    second = create(
        ctx, candidates=[], allow_external=True,
        previous_run_id=first["id"], chat_message="每天一个景点，下午五点结束",
    )
    request = second["request"]
    assert (request["days"], request["stops_per_day"], request["daily_end"]) == (2, 1, "17:00")
    assert request["transport"] == "transit"
    assert [len(day["stops"]) for day in second["result"]["days"]] == [1, 1]
    assert [turn["role"] for turn in second["result"]["chat"]] == ["user", "assistant", "user", "assistant"]
    assert second["saved_artifact_id"] is None


def test_chat_uses_structured_model_fields_only_when_authorized(ctx, monkeypatch):
    from app.agent.travel_chat import TravelTurn

    ctx.provider.key = "explicit-test-only"
    calls = []

    def fake_model(message, context):
        calls.append((message, context))
        return TravelTurn(stops_per_day=1, transport="walking", interests=["美术馆"], rest_minutes=45)

    monkeypatch.setattr("app.agent.travel_chat.model_turn", fake_model)
    create(ctx, candidates=[], allow_external=True, chat_message="想看看广州")
    assert not calls
    plan = create(
        ctx, candidates=[], allow_external=True, allow_model=True, chat_message="想看看广州，每天一个景点",
    )
    assert len(calls) == 1
    assert set(calls[0][1]) <= {*TravelTurn.model_fields, "start_date"}
    assert plan["result"]["intent_source"] == "deepseek"
    assert plan["request"]["stops_per_day"] == 1
    assert plan["request"]["transport"] == "walking"
    assert plan["request"]["rest_minutes"] == 45
    assert [len(day["stops"]) for day in plan["result"]["days"]] == [1, 1]


def test_sightseeing_excludes_services_and_merges_attraction_subareas(ctx, monkeypatch):
    ctx.provider.key = "explicit-test-only"
    sample = ctx.provider.search_pois()[0][0]
    places = [
        replace(sample, id="PARKING", name="广州塔地面停车场", typecode="150905"),
        replace(sample, id="PLAZA", name="广州塔-东广场", typecode="110105"),
        replace(sample, id="TICKET", name="广州塔西售票处", typecode="110000"),
        replace(sample, id="MAIN", name="广州塔", typecode="110202"),
        replace(sample, id="SUB", name="广州塔观景平台", typecode="110200"),
        replace(sample, id="WEST", name="广州塔西", typecode="110200"),
        replace(sample, id="MUSEUM", name="广东省博物馆", typecode="140100"),
    ]
    monkeypatch.setattr(ctx.provider, "search_pois", lambda **_: (places, len(places)))
    query = ctx.client.post("/api/v1/agent/attractions/search", json={
        "keywords": "广州塔", "city_adcode": "440100",
    })
    assert query.status_code == 200, query.text
    expected = {"广州塔", "广东省博物馆"}
    assert {poi["name"] for poi in query.json()["items"]} == expected
    plan = create(ctx, candidates=[], allow_external=True, must_visit=["广州塔"])
    assert {c["name"] for c in plan["result"]["candidates"]} == expected
    assert plan["result"]["verification_status"] == "conditional"
    assert next(c for c in plan["result"]["candidates"] if c["id"] == "amap:MAIN")["must_visit"]


def test_automatic_stop_count_responds_to_time_and_travellers(ctx, monkeypatch):
    ctx.provider.key = "explicit-test-only"
    sample = ctx.provider.search_pois()[0][0]
    places = [replace(sample, id=f"M{i}", name=f"测试博物馆{i}", typecode="140100")
              for i in range(8)]
    monkeypatch.setattr(ctx.provider, "search_pois", lambda **_: (places, len(places)))
    full = create(ctx, candidates=[], allow_external=True,
                  chat_message="广州一天，全天逛博物馆，想多逛")
    short = create(ctx, candidates=[], allow_external=True,
                   chat_message="广州一天，带老人，喜欢博物馆，下午两点前结束")
    assert full["request"].get("stops_per_day") is None
    assert short["request"].get("stops_per_day") is None
    assert short["request"]["rest_minutes"] == 90
    assert short["request"]["daily_end"] == "14:00"
    full_stops = full["result"]["days"][0]["stops"]
    short_stops = short["result"]["days"][0]["stops"]
    assert len(full_stops) > len(short_stops) >= 1
    assert short_stops[-1]["departure"] <= "14:00"


def test_companion_chat_clarifies_campus_and_preserves_plan(ctx):
    initial = create(ctx)
    route = "/api/v1/agent/companion"
    base = {"city_adcode": "440100", "plan_id": initial["id"]}
    question = ctx.client.post(route, json={**base, "message": "然后我也想来中山大学参观参观"})
    assert question.status_code == 200
    reply = question.json()
    assert len(reply["choices"]) == 3
    assert not reply.get("planning_request")
    selected = ctx.client.post(route, json={
        **base, "message": "南校园", "history": [{"role": "assistant", "text": reply["text"]}],
    }).json()
    assert "想去中山大学广州校区南校园" == selected["planning_request"]
    assert "预约" in selected["text"]
    mood = ctx.client.post(route, json={**base, "message": "第一次一个人旅游有一点紧张"}).json()
    assert "担心" in mood["text"]
    assert not mood.get("planning_request")
    attraction = ctx.client.post(route, json={**base, "message": "介绍一下广州塔"}).json()
    assert attraction["sources"][0]["label"] == "广州塔官网"
    with ctx.sessions() as db:
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 1


def test_companion_campus_is_an_explicit_visit_only(ctx, monkeypatch):
    ctx.provider.key = "explicit-test-only"
    sample = ctx.provider.search_pois()[0][0]
    campus = replace(sample, id="CAMPUS", name="中山大学(广州校区南校园)", typecode="141201")
    monkeypatch.setattr(ctx.provider, "search_pois", lambda **_: ([campus, sample], 2))
    first = create(ctx, candidates=[], allow_external=True)
    assert all(stop["name"] != campus.name for day in first["result"]["days"] for stop in day["stops"])
    planned = create(
        ctx, candidates=[], allow_external=True, chat_message="想去中山大学广州校区南校园",
        previous_run_id=first["id"],
    )
    assert any(stop["name"] == campus.name for day in planned["result"]["days"] for stop in day["stops"])
    assert "南校园" in planned["result"]["chat"][-1]["text"]
    assert "预约" in planned["result"]["chat"][-1]["text"]


def test_zero_time_and_nan_coordinates_never_pass_evidence_gate(ctx):
    ctx.provider.key = "explicit-test-only"
    ctx.provider.invalid_duration = True
    run = create(ctx, candidates=[], allow_external=True, interests=["测试"])
    assert all(
        leg["duration_minutes"] is None for day in run["result"]["days"] for leg in day["legs"]
    )
    assert any(
        e.get("details", {}).get("code") == "AMAP_ROUTE_INVALID_EVIDENCE" for e in run["events"]
    )
    ctx.provider.invalid_coordinate = True
    rejected = create(ctx, candidates=[], allow_external=True, interests=["测试"])
    assert rejected["status"] == "needs_input"
    assert rejected["result"]["candidates"] == []


def add_memory(ctx: Context, *, other=False, title="用户真实输入的测试记忆") -> str:
    with ctx.sessions.begin() as db:
        memory = CityMemory(
            user_id=ctx.other_id if other else ctx.owner_id,
            city_id=ctx.city_id,
            title=title,
            body="我在这里写下的一段文字。",
            occurred_at=datetime(2026, 12, 1, 10, tzinfo=UTC),
        )
        db.add(memory)
        db.flush()
        memory_id = memory.id
        for index, scan in enumerate(["clean", "pending"]):
            db.add(
                MediaAsset(
                    memory_id=memory.id,
                    kind="photo",
                    storage_key=f"test/{memory.id}/{index}",
                    original_filename="fixture.jpg",
                    mime_type="image/jpeg",
                    byte_size=100,
                    upload_status="ready",
                    scan_status=scan,
                )
            )
    return str(memory_id)


@pytest.mark.parametrize(("text", "expected"), [
    ("建议游玩 2–3 小时，地铁30分钟", (120, 180)),
    ("游玩时间：一个半小时", (90, 90)),
    ("1小时30分钟", (90, 90)),
    ("建议停留 45 分钟至 1 小时", (45, 60)),
    ("逛了两到三个小时", (120, 180)),
    ("地铁需要 30 分钟，排队 1 小时。", None),
])
def test_guide_duration_requires_visit_context(text, expected):
    if expected is None:
        with pytest.raises(ValueError, match="游玩时长"):
            parse_visit_duration(text)
    else:
        assert parse_visit_duration(text) == expected


def test_guide_references_update_timetable_and_keep_original_estimate(ctx):
    path = "/api/v1/agent/runs"
    existing = create(ctx, days=1, daily_end="21:00")
    references = [
        {"place_name": "用户提供地点0", "excerpt": "建议游玩 2–3 小时",
         "source_url": "https://www.xiaohongshu.com/explore/test-fixture"},
        {"place_name": "用户提供地点0", "excerpt": "停留90分钟"},
        {"place_name": "无对应景点", "excerpt": "游玩半小时"},
    ]
    revision = ctx.client.patch(f"{path}/{existing['id']}/draft", json={
        "expected_revision": existing["revision"], "guide_references": references,
    })
    assert revision.status_code == 200, revision.text
    updated = revision.json()
    stops = updated["result"]["days"][0]["stops"]
    changed = next(stop for stop in stops if stop["name"] == "用户提供地点0")
    assert changed["stay_minutes"] == 120
    assert changed["stay_source"] == "guide_reference"
    assert changed["stay_references"][0] == {
        "from_minutes": 120, "to_minutes": 180,
        "source": "小红书 · 用户提供摘录",
        "source_url": "https://www.xiaohongshu.com/explore/test-fixture",
    }
    assert any("无对应景点" in warning for warning in updated["result"]["warnings"])
    assert updated["saved_artifact_id"] is None
    cleared = ctx.client.patch(f"{path}/{existing['id']}/draft", json={
        "expected_revision": updated["revision"], "guide_references": [],
    })
    assert cleared.status_code == 200, cleared.text
    stops = cleared.json()["result"]["days"][0]["stops"]
    reverted = next(stop for stop in stops if stop["name"] == "用户提供地点0")
    assert reverted["stay_minutes"] == 60
    assert reverted["stay_references"] == []


def test_story_requires_authorization_does_not_invent_sources_or_send_privacy(ctx):
    payload = plan_payload(kind="story", candidates=[])
    assert ctx.client.post("/api/v1/agent/runs", json=payload).status_code == 422
    empty = create(ctx, kind="story", allow_memory_access=True, candidates=[])
    assert empty["status"] == "needs_input"
    assert empty["result"]["story_body"] == ""
    first = add_memory(ctx)
    add_memory(ctx, other=True, title="不得泄露别人的记忆")
    run = create(ctx, kind="story", allow_memory_access=True, candidates=[])
    assert len(run["result"]["source_memories"]) == 1
    assert run["result"]["source_memories"][0]["id"] == first
    assert run["result"]["source_memories"][0]["photo_count"] == 1
    assert "不得泄露" not in str(run)
    assert ctx.provider.calls == 0
    edited = ctx.client.patch(
        f"/api/v1/agent/runs/{run['id']}/draft",
        json={"expected_revision": 1, "story_body": "用户编辑后的故事"},
    ).json()
    assert edited["result"]["edited_by_user"] is True
    body = confirmation(ctx, edited)
    saved = ctx.client.post(f"/api/v1/agent/runs/{run['id']}/confirm", json=body)
    assert saved.status_code == 200
    assert saved.json()["result"]["story_body"] == "用户编辑后的故事"
    with ctx.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CityMemory)) == 2


def test_story_rejects_cross_user_source_and_changed_source_at_confirmation(ctx):
    own = add_memory(ctx)
    other = add_memory(ctx, other=True)
    bad = ctx.client.post(
        "/api/v1/agent/runs",
        json=plan_payload(
            kind="story", allow_memory_access=True, candidates=[], memory_ids=[other]
        ),
    )
    assert bad.status_code == 404
    run = create(ctx, kind="story", allow_memory_access=True, candidates=[], memory_ids=[own])
    body = confirmation(ctx, run)
    with ctx.sessions.begin() as db:
        source = db.get(CityMemory, uuid.UUID(own))
        source.updated_at = datetime.now(UTC) + timedelta(seconds=1)
    response = ctx.client.post(f"/api/v1/agent/runs/{run['id']}/confirm", json=body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STORY_SOURCES_CHANGED"


@pytest.mark.parametrize(
    "update",
    [
        {"days": 5},
        {"daily_start": "18:00", "daily_end": "09:00"},
        {"allow_model": True, "allow_external": False},
        {"kind": "story", "allow_memory_access": True, "allow_external": True},
        {"candidates": [{"name": "bad", "longitude": 200, "latitude": 23}]},
        {"username": "OtherTraveler"},
    ],
)
def test_invalid_or_privacy_violating_requests_rejected(ctx, update):
    payload = copy.deepcopy(plan_payload())
    payload.update(update)
    response = ctx.client.post("/api/v1/agent/runs", json=payload)
    assert response.status_code in (422, 403)


def test_missing_model_falls_back_with_explicit_evidence(ctx):
    run = create(ctx, allow_external=True, allow_model=True)
    assert run["result"]["intent_source"] == "local_rules"
    assert any(
        e.get("details", {}).get("code") == "MODEL_CONFIGURATION_REQUIRED" for e in run["events"]
    )
