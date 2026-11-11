import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    role: str
    is_test_user: bool
    created_at: datetime


class VisitedCityOut(BaseModel):
    adcode: str
    name_zh: str
    name_en: str
    province_zh: str
    longitude: float
    latitude: float
    first_visited_at: datetime
    last_visited_at: datetime
    memory_count: int = 0
    check_in_source: Literal["device", "ip", "manual"] = "device"


class MapStats(BaseModel):
    lit_cities: int
    memories: int
    photos: int
    vlog_minutes: int


class MapOverviewOut(BaseModel):
    username: str
    map_center: tuple[float, float]
    default_zoom: float
    stats: MapStats
    visited_cities: list[VisitedCityOut]


class CheckInCoordinates(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    accuracy_meters: float | None = Field(default=None, ge=0, le=100_000)
    coordinate_system: Literal["WGS84"] = "WGS84"


class CheckInPreviewOut(BaseModel):
    adcode: str
    city_name: str
    province_name: str
    city_center: tuple[float, float]
    map_position: tuple[float, float]
    formatted_address: str
    accuracy_meters: float | None
    already_lit: bool
    location_source: Literal["device", "ip", "manual"] = "device"
    privacy_notice: str = "仅保存城市中心与到访关系，不保存本次精确定位坐标。"


class CheckInConfirmOut(BaseModel):
    status: Literal["created", "updated"]
    city: VisitedCityOut


class ManualCityCheckIn(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)
    adcode: str = Field(pattern=r"^\d{6}$")
    city_name: str = Field(min_length=1, max_length=100)
    province_name: str = Field(default="中国", min_length=1, max_length=100)
    longitude: float = Field(ge=73, le=136)
    latitude: float = Field(ge=3, le=54)
    source: Literal["ip", "manual"]


class MediaAssetOut(BaseModel):
    id: uuid.UUID
    kind: Literal["photo", "vlog"]
    original_filename: str
    mime_type: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    visibility: Literal["private"] = "private"
    upload_status: Literal["ready"] = "ready"
    exif_status: Literal["removed", "not_applicable"] = "not_applicable"
    created_at: datetime


class MediaUploadDraft(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)
    client_request_id: uuid.UUID
    kind: Literal["photo", "vlog"]
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(gt=0)
    visibility: Literal["private"] = "private"


class MediaUploadPreviewOut(BaseModel):
    kind: Literal["photo", "vlog"]
    filename: str
    mime_type: str
    byte_size: int
    quota_remaining_bytes: int
    visibility: Literal["private"] = "private"
    confirmation_notice: str = (
        "确认后文件将直接上传到 Voyaura 私有对象存储；照片会移除 EXIF 元数据。"
    )


class MediaUploadIntentOut(BaseModel):
    status: Literal["created", "existing"]
    asset_id: uuid.UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


class MediaUploadCompleteDraft(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)


class MediaUploadCompleteOut(BaseModel):
    status: Literal["ready", "existing"]
    asset: MediaAssetOut


class CityMemoryItemOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    occurred_at: datetime
    visibility: Literal["private", "shared"]
    media: list[MediaAssetOut]


class CityMemoryStatsOut(BaseModel):
    memories: int
    photos: int
    vlogs: int
    vlog_minutes: int


class CityMemoryDetailOut(BaseModel):
    city: VisitedCityOut
    visit_note: str | None
    stats: CityMemoryStatsOut
    memories: list[CityMemoryItemOut]


class CityMemoryDraft(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)
    client_request_id: uuid.UUID
    title: str = Field(min_length=1, max_length=160)
    body: str | None = Field(default=None, max_length=5000)
    occurred_at: datetime
    visibility: Literal["private", "shared"] = "private"


class CityMemoryPreviewOut(BaseModel):
    city_adcode: str
    city_name: str
    title: str
    body: str | None
    occurred_at: datetime
    visibility: Literal["private", "shared"]
    confirmation_notice: str = "确认后将把这段文字记忆保存到当前城市档案。"


class CityMemoryConfirmOut(BaseModel):
    status: Literal["created", "existing"]
    memory: CityMemoryItemOut


class CityMemoryUpdatePreviewOut(CityMemoryPreviewOut):
    memory_id: uuid.UUID
    confirmation_notice: str = "确认后将更新这段城市记忆，原内容会被替换。"


class CityMemoryUpdateConfirmOut(BaseModel):
    status: Literal["updated", "existing"]
    memory: CityMemoryItemOut


class CityMemoryDeleteDraft(BaseModel):
    username: str = Field(default="AuroraRovella", min_length=1, max_length=64)
    client_request_id: uuid.UUID


class CityMemoryDeletePreviewOut(BaseModel):
    memory_id: uuid.UUID
    city_adcode: str
    city_name: str
    title: str
    occurred_at: datetime
    media_count: int
    confirmation_notice: str = "确认后将删除这段记忆及其关联媒体记录，此操作无法撤销。"


class CityMemoryDeleteConfirmOut(BaseModel):
    status: Literal["deleted", "existing"]
    memory_id: uuid.UUID
    city_adcode: str

