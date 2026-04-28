from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanTemplateBindingCreate(BaseModel):
    template_id: int
    experiment_no: str | None = None
    tube_no: str
    config: dict[str, Any] | None = None
    sort_order: int = 0
    change_note: str = Field(min_length=1)


class CellLabelNodeCreate(BaseModel):
    parent_node_id: int | None = None
    code: str
    name: str
    description: str | None = None
    sort_order: int = 0
    change_note: str = Field(min_length=1)


class MarkerThresholdCreate(BaseModel):
    label_node_id: int | None = None
    marker: str
    channel_name: str
    threshold_type: str = "positive"
    threshold_value: float
    config: dict[str, Any] | None = None
    change_note: str = Field(min_length=1)


class AnalysisPlanCreate(BaseModel):
    name: str
    project_id: int
    description: str | None = None
    change_note: str = Field(min_length=1)


class AnalysisPlanUpdate(BaseModel):
    name: str | None = None
    project_id: int | None = None
    description: str | None = None
    change_note: str = Field(min_length=1)


class AnalysisPlanClone(BaseModel):
    name: str | None = None
    change_note: str = Field(min_length=1)


class PlanTemplateBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    template_id: int
    experiment_no: str | None
    tube_no: str
    config: dict[str, Any] | None
    sort_order: int


class CellLabelNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    parent_node_id: int | None
    code: str
    name: str
    description: str | None
    sort_order: int


class MarkerThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    label_node_id: int | None
    marker: str
    channel_name: str
    threshold_type: str
    threshold_value: float
    config: dict[str, Any] | None


class AnalysisPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project_id: int
    description: str | None
    created_by_user_id: int
    current_version: int
    created_at: datetime
    updated_at: datetime
    template_bindings: list[PlanTemplateBindingResponse]
    cell_label_nodes: list[CellLabelNodeResponse]
    marker_thresholds: list[MarkerThresholdResponse]


class AnalysisPlanVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    version: int
    snapshot_json: dict[str, Any]
    change_note: str
    created_by: int
    created_at: datetime
