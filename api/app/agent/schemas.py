import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.guide_stays import guide_source, parse_visit_duration


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserCandidate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    longitude: float = Field(ge=73, le=136, allow_inf_nan=False)
    latitude: float = Field(ge=3, le=54, allow_inf_nan=False)
    address: str = Field(default="", max_length=240)
    stay_minutes: int = Field(default=60, ge=15, le=480)
    opening_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    opening_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    cost_yuan: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    must_visit: bool = False

    @model_validator(mode="after")
    def check_window(self):
        if bool(self.opening_start) != bool(self.opening_end):
            raise ValueError("开放时间必须同时填写开始与结束。")
        if self.opening_start and self.opening_end and self.opening_start >= self.opening_end:
            raise ValueError("本版本只支持当天、非跨夜开放窗口。")
        return self


class SelectedPoi(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    name: str = Field(min_length=1, max_length=100)


class GuideReference(StrictModel):
    place_name: str = Field(min_length=1, max_length=100)
    excerpt: str = Field(min_length=2, max_length=300)
    source_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def check_evidence(self):
        parse_visit_duration(self.excerpt)
        guide_source(self.source_url)
        return self


class RunCreate(StrictModel):
    client_request_id: uuid.UUID
    kind: Literal["plan", "story"] = "plan"
    goal: str = Field(min_length=2, max_length=1500)
    city_adcode: str = Field(default="440100", pattern=r"^\d{6}$")
    city_name: str = Field(default="广州市", min_length=1, max_length=100)
    start_date: date
    days: int = Field(default=2, ge=1, le=4)
    daily_start: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    daily_end: str = Field(default="18:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    budget_yuan: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    transport: Literal["walking", "transit", "driving"] = "transit"
    pace: Literal["relaxed", "balanced"] = "balanced"
    interests: list[str] = Field(default_factory=list, max_length=3)
    must_visit: list[str] = Field(default_factory=list, max_length=3)
    candidates: list[UserCandidate] = Field(default_factory=list, max_length=12)
    selected_pois: list[SelectedPoi] = Field(default_factory=list, max_length=12)
    allow_external: bool = False
    allow_model: bool = False
    allow_memory_access: bool = False
    memory_ids: list[uuid.UUID] = Field(default_factory=list, max_length=40)
    chat_message: str | None = Field(default=None, min_length=2, max_length=1500)
    previous_run_id: uuid.UUID | None = None
    guide_references: list[GuideReference] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def check_constraints(self):
        if self.daily_start >= self.daily_end:
            raise ValueError("每日结束时间必须晚于开始时间，不支持跨夜。")
        if any(not text.strip() or len(text) > 80 for text in self.interests + self.must_visit):
            raise ValueError("兴趣或必去地点应为1至80字。")
        if self.allow_model and not self.allow_external:
            raise ValueError("使用外部模型前必须同意外部服务调用。")
        if self.selected_pois and (self.kind != "plan" or not self.allow_external):
            raise ValueError("使用已选高德地点需要授权本次行程查询。")
        if len(self.selected_pois) + len(self.candidates) > 12:
            raise ValueError("最多可添加 12 个地点。")
        if self.kind == "story" and not self.allow_memory_access:
            raise ValueError("整理旅行故事前必须授权读取所选城市的旅行记录。")
        if self.kind == "story" and (self.allow_model or self.allow_external):
            raise ValueError("本版本旅行故事仅在本地整理，不向外部传输私人记忆。")
        if self.chat_message and self.kind != "plan":
            raise ValueError("对话规划仅适用于旅行行程。")
        if self.guide_references and self.kind != "plan":
            raise ValueError("游玩攻略仅适用于旅行行程。")
        if self.previous_run_id and not self.chat_message:
            raise ValueError("续聊需要提供本轮消息。")
        return self


class DraftEdit(StrictModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    story_body: str | None = Field(default=None, min_length=1, max_length=16000)
    excluded_candidate_ids: list[str] | None = Field(default=None, max_length=12)
    daily_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    guide_references: list[GuideReference] | None = Field(default=None, max_length=12)


class ConfirmationRequest(StrictModel):
    expected_revision: int = Field(ge=1)


class ConfirmRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    confirmation_token: str = Field(min_length=30, max_length=200)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledge_unverified: bool = False


class RunOut(BaseModel):
    id: uuid.UUID
    kind: Literal["plan", "story"]
    status: str
    revision: int
    title: str
    request: dict
    result: dict
    events: list[dict]
    created_at: datetime
    updated_at: datetime
    saved_artifact_id: uuid.UUID | None = None


class ConfirmationOut(BaseModel):
    confirmation_token: str
    content_digest: str
    expires_at: datetime
    revision: int
    summary: str
    requires_unverified_acknowledgement: bool
