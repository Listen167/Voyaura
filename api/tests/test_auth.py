"""Real bearer boundary tests; no dependency override bypasses authentication."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import City, User

TOKEN = "test-only-private-owner-token-0123456789abcdef"


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add_all(
            [
                User(username="AuroraRovella", display_name="Owner"),
                User(username="OtherTraveler", display_name="Not the owner"),
                City(
                    adcode="440100",
                    name_zh="广州市",
                    name_en="Guangzhou",
                    province_zh="广东省",
                    longitude=113.2644,
                    latitude=23.1291,
                ),
            ]
        )

    def database() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(settings, "auth_token", TOKEN)
    monkeypatch.setattr(settings, "auth_username", "AuroraRovella")
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/map/overview",
        "/api/v1/trips",
        "/api/v1/xiaoxi/planning/capability",
        "/api/v1/users/AuroraRovella",
        "/api/v1/cities/440100/memories",
        "/api/v1/image-styles",
        "/api/v1/tools/routes/capabilities",
    ],
)
def test_private_routes_require_bearer(auth_client: TestClient, path: str) -> None:
    response = auth_client.get(path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_public_health_and_authenticated_identity(auth_client: TestClient) -> None:
    assert auth_client.get("/health").status_code == 200
    assert (
        auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    response = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["username"] == "AuroraRovella"
    assert response.headers["Cache-Control"] == "no-store"
    assert "password_hash" not in response.json()
    assert TOKEN not in response.text


def test_missing_configuration_fails_closed(
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", "")
    response = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/map/overview?username=OtherTraveler",
        "/api/v1/map/overview?username=AuroraRovella&username=OtherTraveler",
        "/api/v1/users/OtherTraveler",
        "/api/v1/image-jobs?username=OtherTraveler",
        "/api/v1/cities/440100/memories?username=OtherTraveler",
    ],
)
def test_cross_user_read_is_forbidden(auth_client: TestClient, path: str) -> None:
    response = auth_client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_cross_user_write_and_default_identity_are_forbidden(
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = auth_client.post(
        "/api/v1/check-ins/manual-confirm",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "username": "OtherTraveler",
            "adcode": "440100",
            "city_name": "伪造名称",
            "province_name": "广东省",
            "longitude": 113.0,
            "latitude": 23.0,
            "source": "manual",
        },
    )
    assert response.status_code == 403
    monkeypatch.setattr(settings, "auth_username", "OtherTraveler")
    # Omitting username cannot accidentally grant access to the old default owner.
    assert (
        auth_client.get(
            "/api/v1/map/overview", headers={"Authorization": f"Bearer {TOKEN}"}
        ).status_code
        == 403
    )


def test_unknown_resource_does_not_reveal_another_users_data(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/api/v1/image-jobs/" + str(uuid.uuid4()),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 404


def test_manual_check_in_does_not_overwrite_existing_city(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/check-ins/manual-confirm",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "username": "AuroraRovella",
            "adcode": "440100",
            "city_name": "伪造名称",
            "province_name": "伪造省份",
            "longitude": 114.0,
            "latitude": 24.0,
            "source": "manual",
        },
    )
    assert response.status_code == 200
    city = response.json()["city"]
    assert city["name_zh"] == "广州市"
    assert city["longitude"] == 113.2644


def test_memory_idempotency_binds_content_and_normalizes_timezone(auth_client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    assert (
        auth_client.post(
            "/api/v1/check-ins/manual-confirm",
            headers=headers,
            json={
                "adcode": "440100",
                "city_name": "广州市",
                "province_name": "广东省",
                "longitude": 113.2644,
                "latitude": 23.1291,
                "source": "manual",
            },
        ).status_code
        == 200
    )
    payload = {
        "client_request_id": str(uuid.uuid4()),
        "title": "测试用记忆",
        "body": "仅用于自动化测试的输入，不是真实旅行经历。",
        "occurred_at": "2026-11-10T12:00:00+08:00",
        "visibility": "private",
    }
    first = auth_client.post(
        "/api/v1/cities/440100/memories/confirm", headers=headers, json=payload
    )
    assert first.status_code == 200
    retry = auth_client.post(
        "/api/v1/cities/440100/memories/confirm",
        headers=headers,
        json={**payload, "occurred_at": "2026-11-10T04:00:00Z"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "existing"
    assert retry.json()["memory"]["id"] == first.json()["memory"]["id"]
    changed = auth_client.post(
        "/api/v1/cities/440100/memories/confirm",
        headers=headers,
        json={**payload, "body": "同一个请求号不能用于另一段文字。"},
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "MEMORY_IDEMPOTENCY_CONFLICT"


def test_planning_preview_requires_owner_bearer(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/xiaoxi/planning/preview", json={"message": "杭州三天"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_formal_trip_user_cannot_be_spoofed(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/api/v1/trips?username=OtherTraveler",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
