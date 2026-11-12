import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="users_username_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="traveler")
    is_test_user: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    city_visits: Mapped[list["CityVisit"]] = relationship(back_populates="user")
    city_memories: Mapped[list["CityMemory"]] = relationship(back_populates="user")


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("adcode", name="cities_adcode_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    adcode: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name_zh: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    province_zh: Mapped[str] = mapped_column(String(100))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)

    visits: Mapped[list["CityVisit"]] = relationship(back_populates="city")
    memories: Mapped[list["CityMemory"]] = relationship(back_populates="city")


class CityVisit(Base):
    __tablename__ = "city_visits"
    __table_args__ = (UniqueConstraint("user_id", "city_id", name="uq_city_visit_user_city"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"))
    first_visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_in_source: Mapped[Literal["device", "ip", "manual"]] = mapped_column(
        String(20),
        default="device",
    )

    user: Mapped[User] = relationship(back_populates="city_visits")
    city: Mapped[City] = relationship(back_populates="visits")


class CityMemory(Base):
    __tablename__ = "city_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_city_memory_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    client_request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    visibility: Mapped[Literal["private", "shared"]] = mapped_column(
        String(20), default="private"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="city_memories")
    city: Mapped[City] = relationship(back_populates="memories")
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
    )


class MemoryMutation(Base):
    __tablename__ = "memory_mutations"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_memory_mutation_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"))
    target_memory_id: Mapped[uuid.UUID] = mapped_column(index=True)
    client_request_id: Mapped[uuid.UUID] = mapped_column()
    operation: Mapped[str] = mapped_column(String(20))
    payload_hash: Mapped[str] = mapped_column(String(64))
    response_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("client_request_id", name="uq_media_asset_client_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("city_memories.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[Literal["photo", "vlog"]] = mapped_column(String(20))
    client_request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    visibility: Mapped[Literal["private"]] = mapped_column(String(20), default="private")
    upload_status: Mapped[Literal["pending", "processing", "ready", "failed"]] = mapped_column(
        String(20), default="ready"
    )
    exif_status: Mapped[Literal["removed", "not_applicable"]] = mapped_column(
        String(24), default="not_applicable"
    )
    scan_status: Mapped[
        Literal["not_scanned", "pending", "scanning", "clean", "infected", "error"]
    ] = mapped_column(String(20), default="not_scanned")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    thumbnail_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memory: Mapped[CityMemory] = relationship(back_populates="media_assets")


class MediaMutation(Base):
    __tablename__ = "media_mutations"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_media_mutation_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"))
    target_memory_id: Mapped[uuid.UUID] = mapped_column(index=True)
    target_asset_id: Mapped[uuid.UUID] = mapped_column(index=True)
    client_request_id: Mapped[uuid.UUID] = mapped_column()
    operation: Mapped[str] = mapped_column(String(20))
    payload_hash: Mapped[str] = mapped_column(String(64))
    response_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImageGenerationJob(Base):
    __tablename__ = "image_generation_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_image_job_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"))
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("city_memories.id", ondelete="CASCADE"), index=True
    )
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    client_request_id: Mapped[uuid.UUID] = mapped_column()
    provider: Mapped[str] = mapped_column(String(40))
    style_id: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    preservation_level: Mapped[Literal["balanced", "high"]] = mapped_column(
        String(20), default="balanced"
    )
    recipe_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    caption_mode: Mapped[Literal["none", "travel_stamp"]] = mapped_column(
        String(24), default="none"
    )
    caption_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    companion_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[Literal["queued", "running", "succeeded", "failed"]] = mapped_column(
        String(20), default="queued", index=True
    )
    provider_job_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    output_storage_key: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    output_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    output_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageJobMutation(Base):
    __tablename__ = "image_job_mutations"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_image_job_mutation_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    client_request_id: Mapped[uuid.UUID] = mapped_column()
    operation: Mapped[str] = mapped_column(String(20))
    response_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

