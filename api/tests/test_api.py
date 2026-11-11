import uuid
from collections.abc import Generator
from datetime import timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.errors import AppError
from app.integrations.amap import ResolvedCity, get_amap_client
from app.integrations.media_storage import StoredObject, get_media_storage
from app.main import app
from app.models import City, CityMemory, MediaAsset, MemoryMutation, User

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class FakeAMapClient:
    def resolve_wgs84_city(self, longitude: float, latitude: float) -> ResolvedCity:
        return ResolvedCity(
            adcode="440100",
            name_zh="广州市",
            province_zh="广东省",
            longitude=113.2644,
            latitude=23.1291,
            formatted_address="广东省广州市",
            gcj_longitude=longitude + 0.004,
            gcj_latitude=latitude - 0.002,
        )


fake_amap_client = FakeAMapClient()
app.dependency_overrides[get_amap_client] = lambda: fake_amap_client


class FakeMediaStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.last_key: str | None = None

    def presigned_put(self, storage_key: str, expires: timedelta) -> str:
        self.last_key = storage_key
        return f"http://storage.test/{storage_key}?expires={int(expires.total_seconds())}"

    def stat(self, storage_key: str) -> StoredObject:
        if storage_key not in self.objects:
            raise AppError("MEDIA_OBJECT_NOT_FOUND", "对象不存在。", status_code=409)
        data, content_type = self.objects[storage_key]
        return StoredObject(size=len(data), content_type=content_type)

    def read(self, storage_key: str, *, max_bytes: int) -> bytes:
        data = self.objects[storage_key][0]
        if len(data) > max_bytes:
            raise AppError("MEDIA_FILE_TOO_LARGE", "文件过大。", status_code=413)
        return data

    def read_prefix(self, storage_key: str, *, length: int = 4096) -> bytes:
        return self.objects[storage_key][0][:length]

    def replace(self, storage_key: str, data: bytes, *, content_type: str) -> None:
        self.objects[storage_key] = (data, content_type)

    def remove(self, storage_key: str) -> None:
        self.objects.pop(storage_key, None)


fake_media_storage = FakeMediaStorage()
app.dependency_overrides[get_media_storage] = lambda: fake_media_storage


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestingSession.begin() as db:
        db.add(
            User(
                username="AuroraRovella",
                display_name="Aurora Rovella",
                role="first_tester",
                is_test_user=True,
            )
        )
    fake_media_storage.objects.clear()
    fake_media_storage.last_key = None
    yield


client = TestClient(app)


def create_memory_for_media() -> str:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    response = client.post(
        "/api/v1/cities/440100/memories/confirm",
        json={
            "username": "AuroraRovella",
            "client_request_id": str(uuid.uuid4()),
            "title": "带媒体的记忆",
            "body": None,
            "occurred_at": "2026-11-10T12:00:00+08:00",
            "visibility": "private",
        },
    )
    return str(response.json()["memory"]["id"])


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_first_tester_profile() -> None:
    response = client.get("/api/v1/users/AuroraRovella")
    assert response.status_code == 200
    assert response.json()["role"] == "first_tester"


def test_empty_map_overview_does_not_invent_visits() -> None:
    response = client.get("/api/v1/map/overview", params={"username": "AuroraRovella"})
    assert response.status_code == 200
    assert response.json()["stats"]["lit_cities"] == 0
    assert response.json()["visited_cities"] == []


def test_check_in_preview_does_not_write_a_visit() -> None:
    response = client.post(
        "/api/v1/check-ins/preview",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    assert response.status_code == 200
    assert response.json()["adcode"] == "440100"
    assert response.json()["already_lit"] is False

    overview = client.get("/api/v1/map/overview", params={"username": "AuroraRovella"})
    assert overview.json()["visited_cities"] == []


def test_check_in_confirm_is_idempotent() -> None:
    payload = {"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13}
    created = client.post("/api/v1/check-ins/confirm", json=payload)
    updated = client.post("/api/v1/check-ins/confirm", json=payload)

    assert created.status_code == 200
    assert created.json()["status"] == "created"
    assert updated.json()["status"] == "updated"

    overview = client.get("/api/v1/map/overview", params={"username": "AuroraRovella"})
    assert overview.json()["stats"]["lit_cities"] == 1
    assert overview.json()["visited_cities"][0]["adcode"] == "440100"
    assert overview.json()["visited_cities"][0]["check_in_source"] == "device"


def test_manual_check_in_preview_does_not_write_and_confirm_is_idempotent() -> None:
    payload = {
        "username": "AuroraRovella",
        "adcode": "110000",
        "city_name": "北京市",
        "province_name": "北京市",
        "longitude": 116.4074,
        "latitude": 39.9042,
        "source": "manual",
    }

    preview = client.post("/api/v1/check-ins/manual-preview", json=payload)
    empty_overview = client.get("/api/v1/map/overview")
    created = client.post("/api/v1/check-ins/manual-confirm", json=payload)
    updated = client.post("/api/v1/check-ins/manual-confirm", json=payload)

    assert preview.status_code == 200
    assert preview.json()["location_source"] == "manual"
    assert empty_overview.json()["visited_cities"] == []
    assert created.json()["status"] == "created"
    assert updated.json()["status"] == "updated"
    assert updated.json()["city"]["check_in_source"] == "manual"

    overview = client.get("/api/v1/map/overview")
    assert overview.json()["stats"]["lit_cities"] == 1
    assert overview.json()["visited_cities"][0]["adcode"] == "110000"


def test_city_memory_detail_is_empty_after_first_check_in() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )

    response = client.get(
        "/api/v1/cities/440100/memories",
        params={"username": "AuroraRovella"},
    )

    assert response.status_code == 200
    assert response.json()["city"]["name_zh"] == "广州市"
    assert response.json()["stats"] == {
        "memories": 0,
        "photos": 0,
        "vlogs": 0,
        "vlog_minutes": 0,
    }
    assert response.json()["memories"] == []


def test_city_memory_detail_and_map_stats_use_real_records() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    with TestingSession.begin() as db:
        user = db.scalar(select(User).where(User.username == "AuroraRovella"))
        city = db.scalar(select(City).where(City.adcode == "440100"))
        assert user is not None and city is not None
        memory = CityMemory(
            user_id=user.id,
            city_id=city.id,
            title="珠江边的晚风",
            body="真实测试记录。",
        )
        memory.media_assets.extend(
            [
                MediaAsset(
                    kind="photo",
                    storage_key="tests/guangzhou/photo.jpg",
                    original_filename="photo.jpg",
                    mime_type="image/jpeg",
                    byte_size=1024,
                    width=1200,
                    height=800,
                ),
                MediaAsset(
                    kind="vlog",
                    storage_key="tests/guangzhou/vlog.mp4",
                    original_filename="vlog.mp4",
                    mime_type="video/mp4",
                    byte_size=4096,
                    duration_seconds=125,
                ),
            ]
        )
        db.add(memory)

    detail = client.get("/api/v1/cities/440100/memories")
    overview = client.get("/api/v1/map/overview")

    assert detail.status_code == 200
    assert detail.json()["stats"] == {
        "memories": 1,
        "photos": 1,
        "vlogs": 1,
        "vlog_minutes": 2,
    }
    assert detail.json()["memories"][0]["title"] == "珠江边的晚风"
    assert overview.json()["stats"]["memories"] == 1
    assert overview.json()["stats"]["photos"] == 1
    assert overview.json()["stats"]["vlog_minutes"] == 2
    assert overview.json()["visited_cities"][0]["memory_count"] == 1


def test_city_memory_preview_does_not_write_and_confirm_is_idempotent() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "title": "  珠江边的晚风  ",
        "body": "  第一次把夜色写进城市档案。  ",
        "occurred_at": "2026-11-10T12:00:00+08:00",
        "visibility": "private",
    }

    preview = client.post("/api/v1/cities/440100/memories/preview", json=payload)
    empty_detail = client.get("/api/v1/cities/440100/memories")
    created = client.post("/api/v1/cities/440100/memories/confirm", json=payload)
    existing = client.post("/api/v1/cities/440100/memories/confirm", json=payload)

    assert preview.status_code == 200
    assert preview.json()["title"] == "珠江边的晚风"
    assert empty_detail.json()["memories"] == []
    assert created.json()["status"] == "created"
    assert existing.json()["status"] == "existing"
    assert existing.json()["memory"]["title"] == "珠江边的晚风"

    detail = client.get("/api/v1/cities/440100/memories")
    overview = client.get("/api/v1/map/overview")
    assert detail.json()["stats"]["memories"] == 1
    assert len(detail.json()["memories"]) == 1
    assert overview.json()["stats"]["memories"] == 1


def test_memory_update_preview_is_read_only_and_confirm_is_idempotent() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    create_payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "title": "旧标题",
        "body": "旧正文",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "visibility": "private",
    }
    created = client.post("/api/v1/cities/440100/memories/confirm", json=create_payload)
    memory_id = created.json()["memory"]["id"]
    update_payload = {
        **create_payload,
        "client_request_id": str(uuid.uuid4()),
        "title": "  新标题  ",
        "body": "  新正文  ",
        "visibility": "shared",
    }

    preview = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/update-preview",
        json=update_payload,
    )
    before_confirm = client.get("/api/v1/cities/440100/memories")
    updated = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/update-confirm",
        json=update_payload,
    )
    existing = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/update-confirm",
        json=update_payload,
    )

    assert preview.status_code == 200
    assert preview.json()["title"] == "新标题"
    assert before_confirm.json()["memories"][0]["title"] == "旧标题"
    assert updated.json()["status"] == "updated"
    assert updated.json()["memory"]["visibility"] == "shared"
    assert existing.json()["status"] == "existing"
    assert existing.json()["memory"]["title"] == "新标题"
    with TestingSession() as db:
        assert len(db.scalars(select(MemoryMutation)).all()) == 1


def test_memory_update_rejects_reused_request_id_with_different_content() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    create_payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "title": "初稿",
        "body": None,
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "visibility": "private",
    }
    created = client.post("/api/v1/cities/440100/memories/confirm", json=create_payload)
    memory_id = created.json()["memory"]["id"]
    mutation_id = str(uuid.uuid4())
    update_payload = {**create_payload, "client_request_id": mutation_id, "title": "第一版修改"}
    client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/update-confirm",
        json=update_payload,
    )

    conflict = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/update-confirm",
        json={**update_payload, "title": "另一版修改"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MEMORY_MUTATION_IDEMPOTENCY_CONFLICT"
    assert conflict.json()["error"]["details"]["client_request_id"] == mutation_id


def test_memory_delete_requires_preview_and_is_idempotent() -> None:
    client.post(
        "/api/v1/check-ins/confirm",
        json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
    )
    create_payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "title": "准备删除的记忆",
        "body": "仍然需要最后确认。",
        "occurred_at": "2026-11-09T12:00:00+08:00",
        "visibility": "private",
    }
    created = client.post("/api/v1/cities/440100/memories/confirm", json=create_payload)
    memory_id = created.json()["memory"]["id"]
    delete_payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
    }

    preview = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/delete-preview",
        json=delete_payload,
    )
    before_confirm = client.get("/api/v1/cities/440100/memories")
    deleted = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/delete-confirm",
        json=delete_payload,
    )
    existing = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/delete-confirm",
        json=delete_payload,
    )

    assert preview.status_code == 200
    assert preview.json()["title"] == "准备删除的记忆"
    assert len(before_confirm.json()["memories"]) == 1
    assert deleted.json()["status"] == "deleted"
    assert existing.json()["status"] == "existing"
    assert client.get("/api/v1/cities/440100/memories").json()["memories"] == []


def test_media_upload_preview_is_read_only() -> None:
    memory_id = create_memory_for_media()
    payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "kind": "photo",
        "filename": "  riverside.jpg  ",
        "mime_type": "image/jpeg",
        "byte_size": 1024,
        "visibility": "private",
    }

    preview = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/media/upload-preview",
        json=payload,
    )

    assert preview.status_code == 200
    assert preview.json()["filename"] == "riverside.jpg"
    assert preview.json()["visibility"] == "private"
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(MediaAsset)) == 0


def test_photo_upload_removes_exif_and_complete_is_idempotent() -> None:
    memory_id = create_memory_for_media()
    image = Image.new("RGB", (32, 24), "#d65d45")
    exif = Image.Exif()
    exif[0x010E] = "private travel note"
    source = BytesIO()
    image.save(source, format="JPEG", exif=exif)
    original = source.getvalue()
    payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "kind": "photo",
        "filename": "riverside.jpg",
        "mime_type": "image/jpeg",
        "byte_size": len(original),
        "visibility": "private",
    }

    intent = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/media/upload-intents",
        json=payload,
    )
    repeated_intent = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/media/upload-intents",
        json=payload,
    )
    assert intent.status_code == 200
    assert intent.json()["status"] == "created"
    assert repeated_intent.json()["status"] == "existing"
    assert client.get("/api/v1/map/overview").json()["stats"]["photos"] == 0
    assert client.get("/api/v1/cities/440100/memories").json()["stats"]["photos"] == 0
    assert fake_media_storage.last_key is not None
    fake_media_storage.objects[fake_media_storage.last_key] = (original, "image/jpeg")

    asset_id = intent.json()["asset_id"]
    complete_url = (
        f"/api/v1/cities/440100/memories/{memory_id}/media/{asset_id}/complete"
    )
    completed = client.post(complete_url, json={"username": "AuroraRovella"})
    existing = client.post(complete_url, json={"username": "AuroraRovella"})

    assert completed.status_code == 200
    assert completed.json()["status"] == "ready"
    assert completed.json()["asset"]["exif_status"] == "removed"
    assert completed.json()["asset"]["width"] == 32
    assert completed.json()["asset"]["height"] == 24
    assert existing.json()["status"] == "existing"
    sanitized = fake_media_storage.objects[fake_media_storage.last_key][0]
    with Image.open(BytesIO(sanitized)) as result:
        assert len(result.getexif()) == 0

    detail = client.get("/api/v1/cities/440100/memories").json()
    assert detail["stats"]["photos"] == 1
    assert detail["memories"][0]["media"][0]["visibility"] == "private"


def test_photo_upload_rejects_mismatched_file_content() -> None:
    memory_id = create_memory_for_media()
    source = BytesIO()
    Image.new("RGB", (8, 8), "white").save(source, format="PNG")
    png_data = source.getvalue()
    payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
        "kind": "photo",
        "filename": "not-really-jpeg.jpg",
        "mime_type": "image/jpeg",
        "byte_size": len(png_data),
        "visibility": "private",
    }
    intent = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/media/upload-intents",
        json=payload,
    )
    assert fake_media_storage.last_key is not None
    fake_media_storage.objects[fake_media_storage.last_key] = (png_data, "image/jpeg")

    response = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/media/{intent.json()['asset_id']}/complete",
        json={"username": "AuroraRovella"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MEDIA_CONTENT_MISMATCH"
    assert fake_media_storage.last_key not in fake_media_storage.objects
    with TestingSession() as db:
        asset = db.scalar(select(MediaAsset))
        assert asset is not None
        assert asset.upload_status == "failed"


def test_memory_delete_removes_owned_storage_objects() -> None:
    memory_id = create_memory_for_media()
    storage_key = "tests/guangzhou/private-photo.jpg"
    fake_media_storage.objects[storage_key] = (b"private", "image/jpeg")
    with TestingSession.begin() as db:
        db.add(
            MediaAsset(
                memory_id=uuid.UUID(memory_id),
                kind="photo",
                storage_key=storage_key,
                original_filename="private-photo.jpg",
                mime_type="image/jpeg",
                byte_size=7,
                upload_status="ready",
                exif_status="removed",
            )
        )
    delete_payload = {
        "username": "AuroraRovella",
        "client_request_id": str(uuid.uuid4()),
    }

    response = client.post(
        f"/api/v1/cities/440100/memories/{memory_id}/delete-confirm",
        json=delete_payload,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert storage_key not in fake_media_storage.objects


def test_unvisited_city_memory_error_is_actionable() -> None:
    with TestingSession.begin() as db:
        db.add(
            City(
                adcode="110100",
                name_zh="北京市",
                name_en="Beijing",
                province_zh="北京市",
                longitude=116.4074,
                latitude=39.9042,
            )
        )

    response = client.get("/api/v1/cities/110100/memories")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CITY_NOT_VISITED"
    assert response.json()["error"]["details"]["adcode"] == "110100"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_provider_error_has_debuggable_shape() -> None:
    class FailingAMapClient:
        def resolve_wgs84_city(self, longitude: float, latitude: float) -> ResolvedCity:
            raise AppError(
                "AMAP_INVALID_SIGNATURE",
                "高德 Web 服务签名验证失败。",
                status_code=502,
                details={"provider_infocode": "10007"},
            )

    app.dependency_overrides[get_amap_client] = lambda: FailingAMapClient()
    try:
        response = client.post(
            "/api/v1/check-ins/preview",
            headers={"Origin": "http://127.0.0.1:5174"},
            json={"username": "AuroraRovella", "longitude": 113.26, "latitude": 23.13},
        )
    finally:
        app.dependency_overrides[get_amap_client] = lambda: fake_amap_client

    error = response.json()["error"]
    assert response.status_code == 502
    assert error["code"] == "AMAP_INVALID_SIGNATURE"
    assert error["details"]["provider_infocode"] == "10007"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5174"

