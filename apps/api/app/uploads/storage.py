from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import urlparse

from fastapi import Depends
from minio import Minio

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str


class ObjectStorage:
    def put_object(
        self,
        *,
        object_key: str,
        data: BinaryIO,
        length: int,
        content_type: str | None,
    ) -> StoredObject:
        raise NotImplementedError


class MinioObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings):
        parsed_endpoint = urlparse(settings.minio_endpoint)
        endpoint = parsed_endpoint.netloc or parsed_endpoint.path
        secure = settings.minio_secure or parsed_endpoint.scheme == "https"
        self.bucket = settings.minio_bucket
        self.client = Minio(
            endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=secure,
        )

    def put_object(
        self,
        *,
        object_key: str,
        data: BinaryIO,
        length: int,
        content_type: str | None,
    ) -> StoredObject:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self.client.put_object(
            self.bucket,
            object_key,
            data,
            length,
            content_type=content_type or "application/octet-stream",
        )
        return StoredObject(bucket=self.bucket, key=object_key)


def get_object_storage(settings: Settings = Depends(get_settings)) -> ObjectStorage:
    return MinioObjectStorage(settings)

