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

