from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.errors import AppError


@dataclass(frozen=True)
class StoredObject:
    size: int
    content_type: str


class MediaStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        self.bucket = bucket
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except (S3Error, OSError) as exc:
            self._unavailable("ensure_bucket", exc)

    def presigned_put(self, storage_key: str, expires: timedelta) -> str:
        self.ensure_bucket()
        try:
            return self.client.presigned_put_object(self.bucket, storage_key, expires=expires)
        except (S3Error, OSError, ValueError) as exc:
            self._unavailable("presign_put", exc)

    def stat(self, storage_key: str) -> StoredObject:
        try:
            result = self.client.stat_object(self.bucket, storage_key)
            return StoredObject(
                size=int(result.size or 0),
                content_type=str(result.content_type or "application/octet-stream"),
            )
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise AppError(
                    "MEDIA_OBJECT_NOT_FOUND",
                    "尚未在对象存储中找到上传文件，请完成上传后重试。",
                    status_code=409,
                    retryable=True,
                ) from exc
            self._unavailable("stat_object", exc)
        except OSError as exc:
            self._unavailable("stat_object", exc)

    def read(self, storage_key: str, *, max_bytes: int) -> bytes:
        response = None
        try:
            response = self.client.get_object(self.bucket, storage_key)
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise AppError(
                    "MEDIA_FILE_TOO_LARGE",
                    "上传文件超过允许大小。",
                    status_code=413,
                    details={"max_bytes": max_bytes},
                )
            return data
        except AppError:
            raise
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise AppError(
                    "MEDIA_OBJECT_NOT_FOUND",
                    "尚未在对象存储中找到上传文件，请完成上传后重试。",
                    status_code=409,
                    retryable=True,
                ) from exc
            self._unavailable("get_object", exc)
        except OSError as exc:
            self._unavailable("get_object", exc)
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def read_prefix(self, storage_key: str, *, length: int = 4096) -> bytes:
        response = None
        try:
            response = self.client.get_object(self.bucket, storage_key, offset=0, length=length)
            return response.read(length)
        except S3Error as exc:
            self._unavailable("get_object_prefix", exc)
        except OSError as exc:
            self._unavailable("get_object_prefix", exc)
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def replace(self, storage_key: str, data: bytes, *, content_type: str) -> None:
        try:
            self.client.put_object(
                self.bucket,
                storage_key,
                io.BytesIO(data),
                len(data),
                content_type=content_type,
            )
        except (S3Error, OSError) as exc:
            self._unavailable("replace_object", exc)

    def remove(self, storage_key: str) -> None:
        try:
            self.client.remove_object(self.bucket, storage_key)
        except (S3Error, OSError) as exc:
            self._unavailable("remove_object", exc)

    @staticmethod
    def _unavailable(operation: str, exc: Exception) -> None:
        raise AppError(
            "MEDIA_STORAGE_UNAVAILABLE",
            "对象存储暂时不可用，请稍后重试。",
            status_code=503,
            details={"operation": operation},
            retryable=True,
        ) from exc


@lru_cache
def get_media_storage() -> MediaStorage:
    return MediaStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )
