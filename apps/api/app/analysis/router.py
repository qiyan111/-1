from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import AnalysisBatch, AnalysisJob, AnalysisStatus
from app.analysis.schemas import (
    AnalysisBatchResponse,
    AnalysisJobLogsResponse,
    StartAnalysisRequest,
)
from app.audit.service import AuditLogService, actor_role_codes
from app.auth.dependencies import get_current_user, get_user_permission_codes, require_permission
from app.db.session import get_db
from app.plans.models import AnalysisPlan
from app.templates.models import AnalysisTemplate
from app.uploads.models import UploadBatch
from app.users.models import User

router = APIRouter(tags=["analysis"])

TERMINAL_STATUSES = {
    AnalysisStatus.COMPLETED.value,
    AnalysisStatus.CANCELLED.value,
}


@router.post(
    "/api/uploads/{upload_batch_id}/start-analysis",
    response_model=AnalysisBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_analysis(
    upload_batch_id: int,
    payload: StartAnalysisRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analysis:execute"))],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    upload_batch = ensure_upload_batch(db, upload_batch_id)
    ensure_can_access_upload_batch(current_user, upload_batch)
    if not upload_batch.files:
        raise HTTPException(status_code=400, detail="Upload batch has no files")
    if payload.plan_id is not None and db.get(AnalysisPlan, payload.plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if payload.template_id is not None and db.get(AnalysisTemplate, payload.template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")

    analysis_batch = AnalysisBatch(
        upload_batch_id=upload_batch.id,
        plan_id=payload.plan_id,
        template_id=payload.template_id,
        requested_by_user_id=current_user.id,
        status=AnalysisStatus.QUEUED.value,
        total_jobs=len(upload_batch.files),
    )
    db.add(analysis_batch)
    db.flush()

    now = datetime.now(timezone.utc).isoformat()
    for data_file in upload_batch.files:
        db.add(
            AnalysisJob(
                analysis_batch_id=analysis_batch.id,
                data_file_id=data_file.id,
                status=AnalysisStatus.QUEUED.value,
                attempt=1,
                logs=[
                    {
                        "timestamp": now,
                        "level": "INFO",
                        "message": "Analysis job queued",
                    }
                ],
            )
        )
    db.commit()
    db.refresh(analysis_batch)
    write_audit(
        db,
        request,
        current_user,
        "analysis.start",
        analysis_batch.id,
        None,
        analysis_batch_snapshot(analysis_batch),
    )
    db.refresh(analysis_batch)
    return analysis_batch


@router.get("/api/analysis/batches", response_model=list[AnalysisBatchResponse])
def list_analysis_batches(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisBatch]:
    statement = select(AnalysisBatch).order_by(AnalysisBatch.id)
    if not is_admin(current_user):
        statement = statement.where(AnalysisBatch.requested_by_user_id == current_user.id)
    return list(db.scalars(statement))


@router.get("/api/analysis/batches/{batch_id}", response_model=AnalysisBatchResponse)
def get_analysis_batch(
    batch_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    batch = ensure_analysis_batch(db, batch_id)
    ensure_can_access_analysis_batch(current_user, batch)
    return batch


@router.post("/api/analysis/batches/{batch_id}/pause", response_model=AnalysisBatchResponse)
def pause_analysis_batch(
    batch_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analysis:execute"))],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    batch = ensure_analysis_batch(db, batch_id)
    ensure_can_access_analysis_batch(current_user, batch)
    if batch.status not in {AnalysisStatus.QUEUED.value, AnalysisStatus.RUNNING.value}:
        raise HTTPException(status_code=409, detail="Only queued or running batches can be paused")
    return transition_batch(db, request, current_user, batch, AnalysisStatus.PAUSED, "analysis.pause")


@router.post("/api/analysis/batches/{batch_id}/resume", response_model=AnalysisBatchResponse)
def resume_analysis_batch(
    batch_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analysis:execute"))],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    batch = ensure_analysis_batch(db, batch_id)
    ensure_can_access_analysis_batch(current_user, batch)
    if batch.status != AnalysisStatus.PAUSED.value:
        raise HTTPException(status_code=409, detail="Only paused batches can be resumed")
    return transition_batch(db, request, current_user, batch, AnalysisStatus.QUEUED, "analysis.resume")


@router.post("/api/analysis/batches/{batch_id}/cancel", response_model=AnalysisBatchResponse)
def cancel_analysis_batch(
    batch_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analysis:execute"))],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    batch = ensure_analysis_batch(db, batch_id)
    ensure_can_access_analysis_batch(current_user, batch)
    if batch.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Terminal batches cannot be cancelled")
    return transition_batch(db, request, current_user, batch, AnalysisStatus.CANCELLED, "analysis.cancel")


@router.post("/api/analysis/batches/{batch_id}/retry", response_model=AnalysisBatchResponse)
def retry_analysis_batch(
    batch_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analysis:execute"))],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisBatch:
    batch = ensure_analysis_batch(db, batch_id)
    ensure_can_access_analysis_batch(current_user, batch)
    failed_jobs = [job for job in batch.jobs if job.status == AnalysisStatus.FAILED.value]
    if not failed_jobs:
        raise HTTPException(status_code=409, detail="No failed jobs to retry")

    before = analysis_batch_snapshot(batch)
    now = datetime.now(timezone.utc).isoformat()
    for job in failed_jobs:
        job.status = AnalysisStatus.QUEUED.value
        job.attempt += 1
        job.error_message = None
        job.logs = [
            *job.logs,
            {
                "timestamp": now,
                "level": "INFO",
                "message": "Failed analysis job re-queued",
            },
        ]
    refresh_batch_counters(batch)
    batch.status = AnalysisStatus.QUEUED.value
    db.commit()
    db.refresh(batch)
    write_audit(db, request, current_user, "analysis.retry", batch.id, before, analysis_batch_snapshot(batch))
    db.refresh(batch)
    return batch


@router.get("/api/analysis/jobs/{job_id}/logs", response_model=AnalysisJobLogsResponse)
def get_analysis_job_logs(
    job_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisJobLogsResponse:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    ensure_can_access_analysis_batch(current_user, job.batch)
    return AnalysisJobLogsResponse(job_id=job.id, logs=job.logs)


def ensure_upload_batch(db: Session, upload_batch_id: int) -> UploadBatch:
    upload_batch = db.get(UploadBatch, upload_batch_id)
    if upload_batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found")
    return upload_batch


def ensure_analysis_batch(db: Session, batch_id: int) -> AnalysisBatch:
    batch = db.get(AnalysisBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Analysis batch not found")
    return batch


def ensure_can_access_upload_batch(current_user: User, upload_batch: UploadBatch) -> None:
    if is_admin(current_user) or upload_batch.uploaded_by_user_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="Insufficient permission")


def ensure_can_access_analysis_batch(current_user: User, batch: AnalysisBatch) -> None:
    if is_admin(current_user) or batch.requested_by_user_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="Insufficient permission")


def is_admin(user: User) -> bool:
    return "admin:write" in get_user_permission_codes(user)


def transition_batch(
    db: Session,
    request: Request,
    current_user: User,
    batch: AnalysisBatch,
    target_status: AnalysisStatus,
    operation_type: str,
) -> AnalysisBatch:
    before = analysis_batch_snapshot(batch)
    now = datetime.now(timezone.utc).isoformat()
    batch.status = target_status.value
    for job in batch.jobs:
        if job.status not in {AnalysisStatus.COMPLETED.value, AnalysisStatus.FAILED.value, AnalysisStatus.CANCELLED.value}:
            job.status = target_status.value
            job.logs = [
                *job.logs,
                {
                    "timestamp": now,
                    "level": "INFO",
                    "message": f"Analysis job status changed to {target_status.value}",
                },
            ]
    refresh_batch_counters(batch)
    db.commit()
    db.refresh(batch)
    write_audit(db, request, current_user, operation_type, batch.id, before, analysis_batch_snapshot(batch))
    db.refresh(batch)
    return batch


def refresh_batch_counters(batch: AnalysisBatch) -> None:
    batch.total_jobs = len(batch.jobs)
    batch.completed_jobs = len([job for job in batch.jobs if job.status == AnalysisStatus.COMPLETED.value])
    batch.failed_jobs = len([job for job in batch.jobs if job.status == AnalysisStatus.FAILED.value])


def analysis_batch_snapshot(batch: AnalysisBatch) -> dict[str, Any]:
    return AnalysisBatchResponse.model_validate(batch).model_dump(mode="json")


def write_audit(
    db: Session,
    request: Request,
    current_user: User,
    operation_type: str,
    resource_id: int,
    before_snapshot: dict[str, Any] | None,
    after_snapshot: dict[str, Any] | None,
) -> None:
    AuditLogService(db).create_log(
        actor_user_id=current_user.id,
        actor_role=actor_role_codes(current_user.roles),
        operation_type=operation_type,
        resource_type="analysis_batch",
        resource_id=str(resource_id),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        operation_result="success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
