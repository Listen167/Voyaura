"""Independent adverse-input checks; providers below are explicit offline test doubles."""

import copy
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agent.models import AgentRun, SavedArtifact
from app.agent.schemas import ConfirmRequest, RunCreate
from app.agent.service import confirm_run, digest, get_run
from app.config import settings
from app.database import Base, get_db
from app.errors import AppError
from app.integrations.amap import AMapClient, get_amap_client
from app.main import app
from app.models import City, CityMemory, MediaAsset, User

TOKEN = "independent-audit-test-token-0123456789abcdef"


class UnavailableMap(AMapClient):
    """Explicit test double; never installed as an application default."""

    def __init__(self):
        super().__init__(key="")
        self.calls = 0

    def search_pois(self, **kwargs):
        self.calls += 1
        raise AppError("AMAP_TIMEOUT", "Explicit offline timeout fixture", retryable=True)


@dataclass
class AuditContext:
    client: TestClient
    sessions: sessionmaker
    provider: UnavailableMap
    owner_id: uuid.UUID


@pytest.fixture
def audit(tmp_path, monkeypatch) -> Generator[AuditContext, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'independent-audit.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        owner = User(username="AuroraRovella", display_name="Independent audit fixture")
        db.add(owner)
        db.flush()
        owner_id = owner.id

    def database():
        with sessions() as db:
            yield db

    saved_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = database
    provider = UnavailableMap()
    app.dependency_overrides[get_amap_client] = lambda: provider
    monkeypatch.setattr(settings, "auth_token", TOKEN)
    monkeypatch.setattr(settings, "auth_username", "AuroraRovella")
    monkeypatch.setenv("VOYAURA_AGENT_LLM_ENABLED", "false")
    try:
        with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
            yield AuditContext(client, sessions, provider, owner_id)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)
        engine.dispose()


def request_body(**updates):
    value = {
        "client_request_id": str(uuid.uuid4()),
        "kind": "plan",
        "goal": "Only explicit offline audit inputs",
        "city_adcode": "440100",
        "city_name": "广州市",
        "start_date": "2026-12-01",
        "days": 2,
        "budget_yuan": 100,
        "candidates": [
            {
                "name": f"Offline input {i}",
                "longitude": 113.3 + i * 0.01,
                "latitude": 23.1 + i * 0.01,
                "stay_minutes": 45,
            }
            for i in range(4)
        ],
    }
    value.update(updates)
    return value


def make_run(audit, **updates):
    response = audit.client.post("/api/v1/agent/runs", json=request_body(**updates))
    assert response.status_code == 201, response.text
    return response.json()


def confirmation_body(audit, run):
    response = audit.client.post(
        f"/api/v1/agent/runs/{run['id']}/confirmation",
        json={"expected_revision": run["revision"]},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    return {
        "expected_revision": run["revision"],
        "confirmation_token": result["confirmation_token"],
        "content_digest": result["content_digest"],
        "acknowledge_unverified": True,
    }


def test_user_only_duplicate_places_are_not_scheduled_twice(audit):
    candidate = request_body()["candidates"][0]
    duplicate = copy.deepcopy(candidate)
    duplicate["must_visit"] = True
    run = make_run(audit, candidates=[candidate, duplicate])
    points = run["result"]["candidates"]
    assert len(points) == 1
    assert points[0]["must_visit"] is True
    assert sum(len(day["stops"]) for day in run["result"]["days"]) == 1
    assert points[0]["source"] == "user_provided"
    assert audit.provider.calls == 0


def test_local_timeline_never_claims_provider_timing(audit):
    run = make_run(audit)
    stops = [stop for day in run["result"]["days"] for stop in day["stops"]]
    assert stops
    assert all(stop["timing_basis"] != "provider" for stop in stops)
    assert audit.provider.calls == 0


def test_repeated_interrupted_run_becomes_observable_failure(audit):
    """A deterministic aged record models a process dying after its initial DB commit."""
    payload = RunCreate.model_validate(request_body())
    # Historical runs omitted the optional POI selection field.
    snapshot = payload.model_dump(
        mode="json", exclude={"selected_pois", "chat_message", "previous_run_id", "guide_references"},
    )
    old = datetime.now(UTC) - timedelta(days=1)
    with audit.sessions.begin() as db:
        row = AgentRun(
            user_id=audit.owner_id,
            client_request_id=payload.client_request_id,
            input_hash=digest(snapshot),
            kind="plan",
            status="running",
            revision=1,
            title="Explicit interrupted-task fixture",
            request_snapshot=snapshot,
            result_snapshot={},
            events=[],
            created_at=old,
            updated_at=old,
        )
        db.add(row)
        db.flush()
        run_id = row.id
    response = audit.client.post("/api/v1/agent/runs", json=snapshot)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["id"] == str(run_id)
    assert run["status"] == "failed"
    assert run["events"]
    assert audit.provider.calls == 0  # Never silently restart potentially charged operations.
    again = audit.client.get(f"/api/v1/agent/runs/{run_id}")
    assert again.status_code == 200
    assert again.json()["status"] == "failed"


def test_stale_confirmation_cannot_report_newer_saved_content_as_its_success(audit):
    """Keep a Session's old run, then emulate a concurrent edit+save in another request."""
    original = make_run(audit)
    original_confirmation = confirmation_body(audit, original)
    with audit.sessions() as stale_db:
        actor = stale_db.get(User, audit.owner_id)
        stale_run = get_run(stale_db, actor, uuid.UUID(original["id"]))
        path = f"/api/v1/agent/runs/{original['id']}"
        changed = audit.client.patch(
            path + "/draft", json={"expected_revision": 1, "title": "A distinct revision"}
        )
        assert changed.status_code == 200
        new_confirmation = confirmation_body(audit, changed.json())
        saved = audit.client.post(path + "/confirm", json=new_confirmation)
        assert saved.status_code == 200
        assert saved.json()["revision"] == 2
        with pytest.raises(AppError) as error:
            confirm_run(
                stale_db, actor, stale_run, ConfirmRequest.model_validate(original_confirmation)
            )
        assert error.value.status_code == 409
    with audit.sessions() as db:
        artifacts = db.scalars(select(SavedArtifact)).all()
        assert len(artifacts) == 1
        assert artifacts[0].title == "A distinct revision"


def test_exhausted_tool_retry_stays_incomplete_and_unconfirmable(audit):
    audit.provider.key = "explicit-offline-fixture-key"
    run = make_run(audit, candidates=[], allow_external=True, interests=["博物馆"])
    assert audit.provider.calls == 2
    assert run["status"] == "needs_input"
    assert run["result"]["verification_status"] == "information_missing"
    events = [e for e in run["events"] if e["tool"] == "amap.search_poi"]
    assert sum(e["status"] == "error" for e in events) == 2
    assert all(e["status"] != "succeeded" for e in events)
    blocked = audit.client.post(
        f"/api/v1/agent/runs/{run['id']}/confirmation", json={"expected_revision": 1}
    )
    assert blocked.status_code == 409


def test_unknown_budget_is_exposed_and_requires_acknowledgement(audit):
    run = make_run(audit, budget_yuan=0)
    result = run["result"]
    assert result["verification_status"] == "conditional"
    assert result["validation"]["unknown_cost_count"] == 4
    assert result["validation"]["known_cost_yuan"] == 0
    body = confirmation_body(audit, run)
    body["acknowledge_unverified"] = False
    denied = audit.client.post(f"/api/v1/agent/runs/{run['id']}/confirm", json=body)
    assert denied.status_code == 422
    with audit.sessions() as db:
        assert db.scalar(select(SavedArtifact)) is None


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_client_coordinates_are_rejected_before_execution(audit, bad_value):
    candidate = request_body()["candidates"][0]
    candidate["longitude"] = bad_value
    # A raw JSON body deliberately exercises the server parser; json= forbids NaN locally.
    import json

    response = audit.client.post(
        "/api/v1/agent/runs",
        content=json.dumps(request_body(candidates=[candidate])),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert audit.provider.calls == 0


def add_private_story_source(audit):
    """An explicit database fixture, not a claim of an actual travel experience."""
    with audit.sessions.begin() as db:
        city = City(
            adcode="440100",
            name_zh="广州市",
            name_en="Guangzhou",
            province_zh="广东省",
            longitude=113.26,
            latitude=23.12,
        )
        db.add(city)
        db.flush()
        memory = CityMemory(
            user_id=audit.owner_id,
            city_id=city.id,
            title="Explicit private fixture",
            body="PRIVATE_FIXTURE_BODY_MUST_WITHDRAW",
            occurred_at=datetime(2026, 12, 1, 10, tzinfo=UTC),
        )
        db.add(memory)
        db.flush()
        return memory.id


def make_story(audit):
    return make_run(audit, kind="story", candidates=[], allow_memory_access=True)


def test_deleted_story_source_withdraws_unsaved_text_and_invalidates_confirmation(audit):
    source_id = add_private_story_source(audit)
    original = make_story(audit)
    path = f"/api/v1/agent/runs/{original['id']}"
    changed = audit.client.patch(
        path + "/draft",
        json={"expected_revision": 1, "story_body": "USER_EDITED_PRIVATE_FIXTURE"},
    )
    assert changed.status_code == 200
    body = confirmation_body(audit, changed.json())
    with audit.sessions.begin() as db:
        db.delete(db.get(CityMemory, source_id))
    withdrawn = audit.client.get(path)
    assert withdrawn.status_code == 200
    value = withdrawn.json()
    assert value["status"] == "needs_input"
    assert value["revision"] == 3
    assert value["result"]["story_body"] == ""
    assert value["result"]["source_memories"] == []
    listed = audit.client.get("/api/v1/agent/runs")
    assert "PRIVATE_FIXTURE_BODY_MUST_WITHDRAW" not in listed.text
    assert "USER_EDITED_PRIVATE_FIXTURE" not in listed.text
    rejected = audit.client.post(path + "/confirm", json=body)
    assert rejected.status_code == 409
    with audit.sessions() as db:
        assert db.scalar(select(SavedArtifact)) is None


def test_ready_media_change_withdraws_unsaved_story(audit):
    source_id = add_private_story_source(audit)
    run = make_story(audit)
    body = confirmation_body(audit, run)
    with audit.sessions.begin() as db:
        db.add(
            MediaAsset(
                memory_id=source_id,
                kind="photo",
                storage_key="explicit-test-only/clean-photo",
                original_filename="fixture.jpg",
                mime_type="image/jpeg",
                byte_size=10,
                upload_status="ready",
                scan_status="clean",
            )
        )
    response = audit.client.post(f"/api/v1/agent/runs/{run['id']}/confirm", json=body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STORY_SOURCES_CHANGED"
    restored = audit.client.get(f"/api/v1/agent/runs/{run['id']}").json()
    assert restored["result"]["story_body"] == ""
    assert audit.provider.calls == 0


def test_saved_story_is_an_explicit_independent_snapshot(audit):
    source_id = add_private_story_source(audit)
    run = make_story(audit)
    body = confirmation_body(audit, run)
    path = f"/api/v1/agent/runs/{run['id']}"
    confirmed = audit.client.post(path + "/confirm", json=body)
    assert confirmed.status_code == 200
    with audit.sessions.begin() as db:
        db.delete(db.get(CityMemory, source_id))
    restored = audit.client.get(path).json()
    assert restored["status"] == "confirmed"
    assert "PRIVATE_FIXTURE_BODY_MUST_WITHDRAW" in restored["result"]["story_body"]
    # This retention behavior must be disclosed; it is not cascade erasure.
    assert restored["saved_artifact_id"] == confirmed.json()["saved_artifact_id"]


def test_invalid_story_source_replay_never_becomes_a_successful_story(audit):
    payload = request_body(
        kind="story", candidates=[], allow_memory_access=True, memory_ids=[str(uuid.uuid4())]
    )
    denied = audit.client.post("/api/v1/agent/runs", json=payload)
    assert denied.status_code == 404
    replay = audit.client.post("/api/v1/agent/runs", json=payload)
    assert replay.status_code == 201
    assert replay.json()["status"] == "failed"
    assert not replay.json()["result"].get("story_body")
    assert replay.json()["saved_artifact_id"] is None
    assert audit.provider.calls == 0
