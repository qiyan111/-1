from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PlotType = Literal["scatter", "density", "histogram", "heatmap", "color_dot"]


class TemplatePlotBase(BaseModel):
    title: str | None = None
    tube_no: str | None = None
    x_channel: str | None = None
    y_channel: str | None = None
    plot_type: PlotType
    config: dict[str, Any] | None = None
    sort_order: int = 0


class TemplateGateBase(BaseModel):
    parent_gate_id: int | None = None
    parent_gate_key: str | None = None
    gate_key: str
    name: str
    gate_type: str
    definition: dict[str, Any]
    sort_order: int = 0


class TemplateLogicGateBase(BaseModel):
    name: str
    expression: str
    definition: dict[str, Any] | None = None
    sort_order: int = 0


class TemplateStatisticBase(BaseModel):
    name: str
    rule_type: str
    formula: str | None = None
    config: dict[str, Any] | None = None
    sort_order: int = 0


class TemplateCreate(BaseModel):
    name: str
    project_code: str
    plots: list[TemplatePlotBase] = Field(default_factory=list)
    gates: list[TemplateGateBase] = Field(default_factory=list)
    logic_gates: list[TemplateLogicGateBase] = Field(default_factory=list)
    statistics: list[TemplateStatisticBase] = Field(default_factory=list)


class TemplateUpdate(TemplateCreate):
    pass


class TemplateClone(BaseModel):
    name: str | None = None


class TemplatePlotResponse(TemplatePlotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TemplateGateResponse(TemplateGateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TemplateLogicGateResponse(TemplateLogicGateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TemplateStatisticResponse(TemplateStatisticBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project_code: str
    created_by_user_id: int
    current_version: int
    created_at: datetime
    updated_at: datetime
    plots: list[TemplatePlotResponse]
    gates: list[TemplateGateResponse]
    logic_gates: list[TemplateLogicGateResponse]
    statistics: list[TemplateStatisticResponse]
