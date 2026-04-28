from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditLogService, actor_role_codes
from app.auth.dependencies import require_permission
from app.db.session import get_db
from app.uploads.models import DataFile, UploadBatch
from app.uploads.schemas import UploadBatchResponse
from app.uploads.storage import ObjectStorage, get_object_storage
from app.users.models import User

ALLOWED_EXTENSIONS = {".fcs", ".lmd", ".csv"}
router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadBatchResponse, status_code=status.HTTP_201_CREATED)
def upload_files(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("upload:write"))],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    files: Annotated[list[UploadFile], File(...)],
) -> UploadBatch:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    invalid_names = [
        file.filename
        for file in files
        if Path(file.filename or "").suffix.lower() not in ALLOWED_EXTENSIONS
    ]
    if invalid_names:
        AuditLogService(db).create_log(
            actor_user_id=current_user.id,
            actor_role=actor_role_codes(current_user.roles),
            operation_type="upload.create",
            resource_type="upload_batch",
            operation_result="failure",
            after_snapshot={"invalid_files": invalid_names},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {', '.join(invalid_names)}",
        )

    batch = UploadBatch(uploaded_by_user_id=current_user.id, status="completed")
    db.add(batch)
    db.flush()

    try:
        for file in files:
            data_file = persist_upload_file(
                db=db,
                storage=storage,
                batch=batch,
                current_user=current_user,
                file=file,
            )
            db.add(data_file)
        db.commit()
        db.refresh(batch)
    except Exception as exc:
        db.rollback()
        AuditLogService(db).create_log(
            actor_user_id=current_user.id,
            actor_role=actor_role_codes(current_user.roles),
            operation_type="upload.create",
            resource_type="upload_batch",
            resource_id=str(batch.id),
            operation_result="failure",
            after_snapshot={"error": str(exc)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=500, detail="Upload failed") from exc

    AuditLogService(db).create_log(
        actor_user_id=current_user.id,
        actor_role=actor_role_codes(current_user.roles),
        operation_type="upload.create",
        resource_type="upload_batch",
        resource_id=str(batch.id),
        operation_result="success",
        after_snapshot={
            "batch_id": batch.id,
            "file_count": len(batch.files),
            "files": [file.original_filename for file in batch.files],
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=UploadBatchResponse)
def get_upload_batch(
    batch_id: int,
    _: Annotated[User, Depends(require_permission("upload:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> UploadBatch:
    batch = db.scalar(select(UploadBatch).where(UploadBatch.id == batch_id))
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found")
    return batch


def persist_upload_file(
    *,
    db: Session,
    storage: ObjectStorage,
    batch: UploadBatch,
    current_user: User,
    file: UploadFile,
) -> DataFile:
    original_filename = file.filename or "unnamed"
    extension = Path(original_filename).suffix.lower()
    object_key = f"raw/{batch.id}/{uuid4().hex}{extension}"

    hasher = hashlib.sha256()
    total_size = 0
    with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024) as buffer:
        while chunk := file.file.read(1024 * 1024):
            total_size += len(chunk)
            hasher.update(chunk)
            buffer.write(chunk)
        buffer.seek(0)
        stored_object = storage.put_object(
            object_key=object_key,
            data=buffer,
            length=total_size,
            content_type=file.content_type,
        )

    try:
        file.file.seek(0)
    except Exception:
        pass

    return DataFile(
        upload_batch_id=batch.id,
        uploaded_by_user_id=current_user.id,
        original_filename=original_filename,
        file_extension=extension,
        content_type=file.content_type,
        object_bucket=stored_object.bucket,
        object_key=stored_object.key,
        file_size=total_size,
        sha256=hasher.hexdigest(),
    )
