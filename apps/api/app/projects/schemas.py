from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ExperimentCreate(BaseModel):
    project_id: int
    experiment_no: str
    name: str | None = None


class ExperimentResponse(ExperimentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SampleCreate(BaseModel):
    experiment_id: int
    sample_no: str
    subject_identifier: str | None = None


class SampleResponse(SampleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class TubeCreate(BaseModel):
    sample_id: int
    tube_no: str
    group_name: str | None = None
    experimental_condition: str | None = None
    antibody_info: dict[str, Any] | None = None
    data_file_ids: list[int] = Field(default_factory=list)


class TubeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sample_id: int
    tube_no: str
    group_name: str | None
    experimental_condition: str | None
    antibody_info: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ChannelCreate(BaseModel):
    name: str
    detector: str | None = None
    fluorochrome: str | None = None
    marker: str | None = None
    channel_index: int | None = None


class ChannelResponse(ChannelCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tube_id: int


class MarkerMappingCreate(BaseModel):
    marker: str
    channel_name: str
    fluorochrome: str | None = None


class MarkerMappingResponse(MarkerMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tube_id: int
