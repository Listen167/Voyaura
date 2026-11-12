from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://voyaura:voyaura_dev_only@127.0.0.1:5433/voyaura"
    )
    cors_origins: str = "http://127.0.0.1:5174,http://localhost:5174"
    amap_web_key: str = ""
    amap_web_private_key: str = ""
    amap_js_key: str = ""
    amap_security_code: str = ""
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "voyaura"
    minio_secret_key: str = "voyaura_minio_dev_only"
    minio_bucket: str = "voyaura-media"
    minio_secure: bool = False
    media_photo_max_bytes: int = 20 * 1024 * 1024
    media_vlog_max_bytes: int = 500 * 1024 * 1024
    media_user_quota_bytes: int = 2 * 1024 * 1024 * 1024
    media_upload_ttl_minutes: int = 15
    redis_url: str = "redis://127.0.0.1:6379/0"
    media_queue_key: str = "voyaura:media:jobs"
    media_scanner_provider: str = "windows_defender"
    windows_defender_path: str = ""
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    media_cleanup_interval_seconds: int = 60 * 60
    media_cleanup_batch_size: int = 100
    image_provider: str = "disabled"
    image_queue_key: str = "voyaura:image:jobs"
    image_caption_font_path: str = ""
    xiaoxi_photo_asset_path: str = ""
    xiaoxi_photo_asset_version: str = "unconfigured"
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflow_path: str = ""
    comfyui_input_node_id: str = ""
    comfyui_positive_prompt_node_id: str = ""
    comfyui_negative_prompt_node_id: str = ""
    comfyui_output_node_id: str = ""
    comfyui_timeout_seconds: int = 300
    comfyui_poll_interval_seconds: float = 1.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOYAURA_",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

