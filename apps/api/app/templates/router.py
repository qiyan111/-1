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
    AnalysisTemplateVersion,
    TemplateGate,
    TemplateLogicGate,
    TemplatePlot,
    TemplateStatistic,
)
from app.templates.schemas import (
    TemplateClone,
    TemplateCreate,
    TemplateResponse,
    TemplateRollback,
    TemplateUpdate,
    TemplateVersionResponse,
)
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
    version = create_template_version(db, template, payload.change_note, current_user.id)
    after = template_snapshot(template)
    write_audit(db, request, current_user, "template.create", template.id, None, after)
    write_audit(db, request, current_user, "template.version.create", version.id, None, version_snapshot(version))
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
    version = create_template_version(db, template, payload.change_note, current_user.id)
    after = template_snapshot(template)
    write_audit(db, request, current_user, "template.update", template.id, before, after)
    write_audit(db, request, current_user, "template.version.create", version.id, None, version_snapshot(version))
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
    payload: TemplateClone,
) -> AnalysisTemplate:
    source = ensure_template(db, template_id)
    source_snapshot = template_snapshot(source)
    clone_payload = TemplateCreate(
        name=payload.name if payload.name else f"{source.name} Copy",
        project_code=source.project_code,
        change_note=payload.change_note,
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
    version = create_template_version(db, template, payload.change_note, current_user.id)
    after = template_snapshot(template)
    write_audit(db, request, current_user, "template.clone", template.id, source_snapshot, after)
    write_audit(db, request, current_user, "template.version.create", version.id, None, version_snapshot(version))
    return template


@router.get("/api/templates/{template_id}/versions", response_model=list[TemplateVersionResponse])
def list_template_versions(
    template_id: int,
    request: Request,
    current_user: Annotated[User, Depends(read_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisTemplateVersion]:
    ensure_template(db, template_id)
    versions = list(
        db.scalars(
            select(AnalysisTemplateVersion)
            .where(AnalysisTemplateVersion.template_id == template_id)
            .order_by(AnalysisTemplateVersion.version)
        )
    )
    write_audit(
        db,
        request,
        current_user,
        "template.version.list",
        template_id,
        None,
        {"version_ids": [version.id for version in versions]},
    )
    return versions


@router.get("/api/templates/{template_id}/versions/{version_id}", response_model=TemplateVersionResponse)
def get_template_version(
    template_id: int,
    version_id: int,
    request: Request,
    current_user: Annotated[User, Depends(read_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisTemplateVersion:
    version = ensure_template_version(db, template_id, version_id)
    write_audit(db, request, current_user, "template.version.read", version.id, None, version_snapshot(version))
    return version


@router.post("/api/templates/{template_id}/rollback", response_model=TemplateResponse)
def rollback_template(
    template_id: int,
    payload: TemplateRollback,
    request: Request,
    current_user: Annotated[User, Depends(write_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisTemplate:
    template = ensure_template(db, template_id)
    version = ensure_template_version(db, template_id, payload.version_id)
    before = template_snapshot(template)
    replace_template(template, payload_from_snapshot(version.snapshot_json, payload.change_note))
    template.current_version += 1
    db.commit()
    db.refresh(template)
    new_version = create_template_version(db, template, payload.change_note, current_user.id)
    after = template_snapshot(template)
    write_audit(db, request, current_user, "template.rollback", template.id, before, after)
    write_audit(db, request, current_user, "template.version.create", new_version.id, version_snapshot(version), version_snapshot(new_version))
    return template


@router.get("/api/templates/{template_id}/diff")
def diff_template_versions(
    template_id: int,
    from_version_id: int,
    to_version_id: int,
    request: Request,
    current_user: Annotated[User, Depends(read_templates)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    from_version = ensure_template_version(db, template_id, from_version_id)
    to_version = ensure_template_version(db, template_id, to_version_id)
    diff = {
        "template_id": template_id,
        "from_version_id": from_version_id,
        "to_version_id": to_version_id,
        "plots": compare_collection(from_version.snapshot_json, to_version.snapshot_json, "plots", "title"),
        "gates": compare_collection(from_version.snapshot_json, to_version.snapshot_json, "gates", "gate_key"),
        "logic_gates": compare_collection(from_version.snapshot_json, to_version.snapshot_json, "logic_gates", "name"),
        "statistics": compare_collection(from_version.snapshot_json, to_version.snapshot_json, "statistics", "name"),
        "channel_config": compare_channel_config(from_version.snapshot_json, to_version.snapshot_json),
    }
    write_audit(db, request, current_user, "template.version.diff", template_id, None, diff)
    return diff


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


def version_snapshot(version: AnalysisTemplateVersion) -> dict[str, Any]:
    return TemplateVersionResponse.model_validate(version).model_dump(mode="json")


def create_template_version(
    db: Session,
    template: AnalysisTemplate,
    change_note: str,
    created_by: int,
) -> AnalysisTemplateVersion:
    version = AnalysisTemplateVersion(
        template_id=template.id,
        version=template.current_version,
        snapshot_json=template_snapshot(template),
        change_note=change_note,
        created_by=created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def ensure_template_version(db: Session, template_id: int, version_id: int) -> AnalysisTemplateVersion:
    version = db.get(AnalysisTemplateVersion, version_id)
    if version is None or version.template_id != template_id:
        raise HTTPException(status_code=404, detail="Template version not found")
    return version


def payload_from_snapshot(snapshot: dict[str, Any], change_note: str) -> TemplateUpdate:
    return TemplateUpdate(
        name=snapshot["name"],
        project_code=snapshot["project_code"],
        change_note=change_note,
        plots=[strip_child_ids(plot) for plot in snapshot.get("plots", [])],
        gates=[
            {**strip_child_ids(gate), "parent_gate_id": None}
            for gate in snapshot.get("gates", [])
        ],
        logic_gates=[strip_child_ids(logic_gate) for logic_gate in snapshot.get("logic_gates", [])],
        statistics=[strip_child_ids(statistic) for statistic in snapshot.get("statistics", [])],
    )


def strip_child_ids(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "id"}


def compare_collection(
    from_snapshot: dict[str, Any],
    to_snapshot: dict[str, Any],
    collection_name: str,
    key_name: str,
) -> dict[str, list[dict[str, Any]]]:
    from_items = {item_identity(item, key_name): normalize_item(item) for item in from_snapshot.get(collection_name, [])}
    to_items = {item_identity(item, key_name): normalize_item(item) for item in to_snapshot.get(collection_name, [])}
    from_keys = set(from_items)
    to_keys = set(to_items)
    return {
        "added": [to_items[key] for key in sorted(to_keys - from_keys)],
        "removed": [from_items[key] for key in sorted(from_keys - to_keys)],
        "modified": [
            {"key": key, "before": from_items[key], "after": to_items[key]}
            for key in sorted(from_keys & to_keys)
            if from_items[key] != to_items[key]
        ],
    }


def compare_channel_config(from_snapshot: dict[str, Any], to_snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return compare_collection(
        {"channel_config": [plot_channel_config(plot) for plot in from_snapshot.get("plots", [])]},
        {"channel_config": [plot_channel_config(plot) for plot in to_snapshot.get("plots", [])]},
        "channel_config",
        "key",
    )


def plot_channel_config(plot: dict[str, Any]) -> dict[str, Any]:
    title = plot.get("title") or f"plot-{plot.get('sort_order', 0)}"
    return {
        "key": title,
        "tube_no": plot.get("tube_no"),
        "x_channel": plot.get("x_channel"),
        "y_channel": plot.get("y_channel"),
        "plot_type": plot.get("plot_type"),
    }


def item_identity(item: dict[str, Any], key_name: str) -> str:
    return str(item.get(key_name) or item.get("sort_order") or item.get("id"))


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "id"}


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
