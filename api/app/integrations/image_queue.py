from __future__ import annotations

from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import AppError


class ImageJobQueue:
    def __init__(self, redis_url: str, queue_key: str) -> None:
        self.queue_key = queue_key
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, job_id: str) -> None:
        try:
            self.client.rpush(self.queue_key, job_id)
        except RedisError as exc:
            raise AppError(
                "IMAGE_QUEUE_UNAVAILABLE",
                "图片生成队列暂时不可用，请稍后重试。",
                status_code=503,
                details={"queue": self.queue_key},
                retryable=True,
            ) from exc

    def dequeue(self, timeout_seconds: int = 5) -> str | None:
        try:
            item = self.client.blpop(self.queue_key, timeout=timeout_seconds)
        except RedisError as exc:
            raise AppError(
                "IMAGE_QUEUE_UNAVAILABLE",
                "图片生成队列暂时不可用，请稍后重试。",
                status_code=503,
                details={"queue": self.queue_key},
                retryable=True,
            ) from exc
        return str(item[1]) if item else None


@lru_cache
def get_image_queue() -> ImageJobQueue:
    return ImageJobQueue(settings.redis_url, settings.image_queue_key)
