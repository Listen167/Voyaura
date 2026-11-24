from __future__ import annotations

from typing import Literal

import pytest
from fastapi.testclient import TestClient

from app.auth import get_actor
from app.integrations.travel_llm import (
    TravelPlanningExtractor,
    get_travel_planning_extractor,
)
from app.main import app
from app.models import User
from app.xiaoxi_planning import (
    AttractionHypothesis,
    ModelPlanningDraft,
    PlanningIntent,
    PoiSearchTheme,
)


@pytest.fixture(autouse=True)
def explicit_provider_unit_actor():
    previous = app.dependency_overrides.get(get_actor)
    app.dependency_overrides[get_actor] = lambda: User(username="AuroraRovella")
    yield
    if previous is None:
        app.dependency_overrides.pop(get_actor, None)
    else:
        app.dependency_overrides[get_actor] = previous

class FakePlanningExtractor:
    provider: Literal["deepseek"] = "deepseek"
    model = "deepseek-chat-test"

    def __init__(self, draft: ModelPlanningDraft, *, available: bool = True) -> None:
        self.available = available
        self.draft = draft
        self.calls: list[tuple[str, dict[str, object]]] = []

    def extract(self, message: str, confirmed_context: dict[str, object]) -> ModelPlanningDraft:
        self.calls.append((message, confirmed_context))
        return self.draft


def _ready_draft() -> ModelPlanningDraft:
    return ModelPlanningDraft(
        assistant_summary="我先按三天轻松摄影旅行整理候选，再交给高德核验。",
        intent=PlanningIntent(
            city_name="上海市",
            day_count=2,
            party_type="solo",
            pace="balanced",
            interests=["摄影", "摄影", "历史建筑"],
            transport_modes=["transit"],
        ),
        attraction_hypotheses=[
            AttractionHypothesis(
                name="西湖风景名胜区",
                category="photography",
                reason="可作为摄影主题候选，具体游览条件待核验。",
                priority=5,
            )
        ],
        search_themes=[
            PoiSearchTheme(
                keyword="杭州 摄影景点",
                category="photography",
                reason="扩展适合拍摄的地点候选。",
                desired_count=10,
            )
        ],
        assumptions=["尚未提供住宿区域。"],
    )


def _override(extractor: FakePlanningExtractor) -> None:
    app.dependency_overrides[get_travel_planning_extractor] = lambda: extractor


def _restore() -> None:
    app.dependency_overrides.pop(get_travel_planning_extractor, None)


def test_planning_preview_uses_confirmed_context_over_model_guess() -> None:
    extractor = FakePlanningExtractor(_ready_draft())
    _override(extractor)
    try:
        response = TestClient(app).post(
            "/api/v1/xiaoxi/planning/preview",
            json={
                "message": "我想一个人轻松拍照",
                "context": {
                    "city_name": "杭州市",
                    "city_adcode": "330100",
                    "day_count": 3,
                    "pace": "relaxed",
                },
            },
        )
    finally:
        _restore()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_poi_search"
    assert payload["requirements"]["city_name"] == "杭州市"
    assert payload["requirements"]["day_count"] == 3
    assert payload["requirements"]["pace"] == "relaxed"
    assert payload["requirements"]["interests"] == ["摄影", "历史建筑"]
    assert payload["city_adcode"] == "330100"
    assert payload["candidate_target_count"] == 30
    assert payload["recommended_daily_attractions"] == {"min": 2, "max": 3}
    assert payload["attraction_hypotheses"][0]["name"] == "西湖风景名胜区"
    assert "高德" in payload["warnings"][1]
    assert extractor.calls == [
        (
            "我想一个人轻松拍照",
            {
                "city_name": "杭州市",
                "city_adcode": "330100",
                "day_count": 3,
                "pace": "relaxed",
            },
        )
    ]


def test_planning_preview_requests_required_fields_and_discards_candidates() -> None:
    draft = _ready_draft().model_copy(
        update={
            "assistant_summary": "我还需要确认目的地和天数。",
            "intent": PlanningIntent(),
        }
    )
    extractor = FakePlanningExtractor(draft)
    _override(extractor)
    try:
        response = TestClient(app).post(
            "/api/v1/xiaoxi/planning/preview",
            json={"message": "帮我安排一次轻松的旅行"},
        )
    finally:
        _restore()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_clarification"
    assert payload["missing_fields"] == ["city_name", "day_count"]
    assert payload["clarification_questions"] == ["你想去哪个城市旅行？", "这次计划安排几天？"]
    assert payload["candidate_target_count"] == 0
    assert payload["attraction_hypotheses"] == []
    assert payload["search_themes"] == []


def test_planning_capability_reports_model_configuration() -> None:
    extractor = FakePlanningExtractor(_ready_draft(), available=False)
    _override(extractor)
    try:
        response = TestClient(app).get("/api/v1/xiaoxi/planning/capability")
    finally:
        _restore()

    assert response.status_code == 200
    assert response.json() == {
        "provider": "deepseek",
        "model": "deepseek-chat-test",
        "available": False,
        "state": "configuration_required",
        "structured_output": True,
        "notice": "需要在 API 环境配置 VOYAURA_DEEPSEEK_API_KEY。",
    }


def test_planning_preview_rejects_blank_message_before_model_call() -> None:
    extractor: TravelPlanningExtractor = FakePlanningExtractor(_ready_draft())
    app.dependency_overrides[get_travel_planning_extractor] = lambda: extractor
    try:
        response = TestClient(app).post(
            "/api/v1/xiaoxi/planning/preview",
            json={"message": "   "},
        )
    finally:
        _restore()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
