from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StartAnalysisRequest(BaseModel):
    plan_id: int | None = None
    template_id: int | None = None


class AnalysisJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_batch_id: int
    data_file_id: int
    retry_of_job_id: int | None
    status: str
    attempt: int
    logs: list[dict[str, Any]]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AnalysisBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_batch_id: int
    plan_id: int | None
    template_id: int | None
    requested_by_user_id: int
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    created_at: datetime
    updated_at: datetime
    jobs: list[AnalysisJobResponse]


class AnalysisJobLogsResponse(BaseModel):
    job_id: int
    logs: list[dict[str, Any]]
