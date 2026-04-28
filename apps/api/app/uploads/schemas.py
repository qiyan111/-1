from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DataFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    file_extension: str
    content_type: str | None
    object_bucket: str
    object_key: str
    file_size: int
    sha256: str
    uploaded_by_user_id: int
    uploaded_at: datetime


class UploadBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    uploaded_by_user_id: int
    created_at: datetime
    files: list[DataFileResponse]

