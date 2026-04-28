from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditLogService, actor_role_codes
from app.auth.dependencies import require_permission
from app.db.session import get_db
from app.templates.models import (
    AnalysisTemplate,
    TemplateGate,
    TemplateLogicGate,
    TemplatePlot,
    TemplateStatistic,
)
from app.templates.schemas import TemplateClone, TemplateCreate, TemplateResponse, TemplateUpdate
from app.users.models import User

router = APIRouter(tags=["templates"])
read_templates = require_permission("template:read")
write_templates = require_permission("template:write")


@router.get("/api/templates", response_model=list[TemplateResponse])
def list_templates(
    _: Annotated[User, Depends(read_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisTemplate]:
    return list(db.scalars(select(AnalysisTemplate).order_by(AnalysisTemplate.id)))


@router.post("/api/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisTemplate:
    template = build_template(payload, created_by_user_id=current_user.id)
    db.add(template)
    db.commit()
    db.refresh(template)
    write_audit(db, request, current_user, "template.create", template.id, None, template_snapshot(template))
    return template


@router.get("/api/templates/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    _: Annotated[User, Depends(read_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisTemplate:
    return ensure_template(db, template_id)


@router.put("/api/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    request: Request,
    current_user: Annotated[User, Depends(write_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisTemplate:
    template = ensure_template(db, template_id)
    before = template_snapshot(template)
    replace_template(template, payload)
    template.current_version += 1
    db.commit()
    db.refresh(template)
    write_audit(db, request, current_user, "template.update", template.id, before, template_snapshot(template))
    return template


@router.delete("/api/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    request: Request,
    current_user: Annotated[User, Depends(write_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    template = ensure_template(db, template_id)
    before = template_snapshot(template)
    db.delete(template)
    db.commit()
    write_audit(db, request, current_user, "template.delete", template_id, before, None)


@router.post("/api/templates/{template_id}/clone", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def clone_template(
    template_id: int,
    request: Request,
    current_user: Annotated[User, Depends(write_templates)],
    db: Annotated[Session, Depends(get_db)],
    payload: TemplateClone | None = None,
) -> AnalysisTemplate:
    source = ensure_template(db, template_id)
    source_snapshot = template_snapshot(source)
    clone_payload = TemplateCreate(
        name=payload.name if payload and payload.name else f"{source.name} Copy",
        project_code=source.project_code,
        plots=source_snapshot["plots"],
        gates=[
            {**gate, "parent_gate_id": None}
            for gate in source_snapshot["gates"]
        ],
        logic_gates=source_snapshot["logic_gates"],
        statistics=source_snapshot["statistics"],
    )
    template = build_template(clone_payload, created_by_user_id=current_user.id)
    db.add(template)
    db.commit()
    db.refresh(template)
    write_audit(db, request, current_user, "template.clone", template.id, source_snapshot, template_snapshot(template))
    return template


def ensure_template(db: Session, template_id: int) -> AnalysisTemplate:
    template = db.get(AnalysisTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


def build_template(payload: TemplateCreate, *, created_by_user_id: int) -> AnalysisTemplate:
    template = AnalysisTemplate(
        name=payload.name,
        project_code=payload.project_code,
        created_by_user_id=created_by_user_id,
        current_version=1,
    )
    fill_template_children(template, payload)
    return template


def replace_template(template: AnalysisTemplate, payload: TemplateUpdate) -> None:
    template.name = payload.name
    template.project_code = payload.project_code
    template.plots.clear()
    template.gates.clear()
    template.logic_gates.clear()
    template.statistics.clear()
    fill_template_children(template, payload)


def fill_template_children(template: AnalysisTemplate, payload: TemplateCreate) -> None:
    template.plots.extend(TemplatePlot(**plot.model_dump()) for plot in payload.plots)
    template.gates.extend(TemplateGate(**gate.model_dump()) for gate in payload.gates)
    template.logic_gates.extend(
        TemplateLogicGate(**logic_gate.model_dump())
        for logic_gate in payload.logic_gates
    )
    template.statistics.extend(
        TemplateStatistic(**statistic.model_dump())
        for statistic in payload.statistics
    )


def template_snapshot(template: AnalysisTemplate) -> dict[str, Any]:
    return TemplateResponse.model_validate(template).model_dump(mode="json")


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
        resource_type="analysis_template",
        resource_id=str(resource_id),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        operation_result="success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
