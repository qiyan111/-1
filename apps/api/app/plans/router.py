from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditLogService, actor_role_codes
from app.auth.dependencies import get_current_user, require_any_permission
from app.db.session import get_db
from app.plans.models import (
    AnalysisPlan,
    AnalysisPlanVersion,
    CellLabelNode,
    MarkerThreshold,
    PlanTemplateBinding,
)
from app.plans.schemas import (
    AnalysisPlanClone,
    AnalysisPlanCreate,
    AnalysisPlanResponse,
    AnalysisPlanUpdate,
    AnalysisPlanVersionResponse,
    CellLabelNodeCreate,
    CellLabelNodeResponse,
    MarkerThresholdCreate,
    MarkerThresholdResponse,
    PlanTemplateBindingCreate,
    PlanTemplateBindingResponse,
)
from app.projects.models import Project
from app.templates.models import AnalysisTemplate
from app.users.models import User

router = APIRouter(tags=["plans"])
write_plans = require_any_permission({"template:write", "admin:write"})


@router.get("/api/plans", response_model=list[AnalysisPlanResponse])
def list_plans(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisPlan]:
    return list(db.scalars(select(AnalysisPlan).order_by(AnalysisPlan.id)))


@router.post("/api/plans", response_model=AnalysisPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: AnalysisPlanCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisPlan:
    ensure_exists(db, Project, payload.project_id, "Project not found")
    plan = AnalysisPlan(
        name=payload.name,
        project_id=payload.project_id,
        description=payload.description,
        created_by_user_id=current_user.id,
        current_version=1,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    version = create_plan_version(db, plan, payload.change_note, current_user.id)
    after = plan_snapshot(plan)
    write_audit(db, request, current_user, "plan.create", plan.id, None, after)
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return plan


@router.get("/api/plans/{plan_id}", response_model=AnalysisPlanResponse)
def get_plan(
    plan_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisPlan:
    return ensure_plan(db, plan_id)


@router.put("/api/plans/{plan_id}", response_model=AnalysisPlanResponse)
def update_plan(
    plan_id: int,
    payload: AnalysisPlanUpdate,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisPlan:
    plan = ensure_plan(db, plan_id)
    before = plan_snapshot(plan)
    if payload.project_id is not None:
        ensure_exists(db, Project, payload.project_id, "Project not found")
        plan.project_id = payload.project_id
    if payload.name is not None:
        plan.name = payload.name
    if payload.description is not None:
        plan.description = payload.description
    plan.current_version += 1
    db.commit()
    db.refresh(plan)
    version = create_plan_version(db, plan, payload.change_note, current_user.id)
    after = plan_snapshot(plan)
    write_audit(db, request, current_user, "plan.update", plan.id, before, after)
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return plan


@router.post("/api/plans/{plan_id}/clone", response_model=AnalysisPlanResponse, status_code=status.HTTP_201_CREATED)
def clone_plan(
    plan_id: int,
    payload: AnalysisPlanClone,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisPlan:
    source = ensure_plan(db, plan_id)
    before = plan_snapshot(source)
    clone = AnalysisPlan(
        name=payload.name if payload.name else f"{source.name} Copy",
        project_id=source.project_id,
        description=source.description,
        created_by_user_id=current_user.id,
        current_version=1,
    )
    db.add(clone)
    db.flush()
    clone_template_bindings(source, clone)
    label_map = clone_cell_label_nodes(source, clone, db)
    clone_marker_thresholds(source, clone, label_map)
    db.commit()
    db.refresh(clone)
    version = create_plan_version(db, clone, payload.change_note, current_user.id)
    after = plan_snapshot(clone)
    write_audit(db, request, current_user, "plan.clone", clone.id, before, after)
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return clone


@router.get("/api/plans/{plan_id}/versions", response_model=list[AnalysisPlanVersionResponse])
def list_plan_versions(
    plan_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisPlanVersion]:
    ensure_plan(db, plan_id)
    return list(
        db.scalars(
            select(AnalysisPlanVersion)
            .where(AnalysisPlanVersion.plan_id == plan_id)
            .order_by(AnalysisPlanVersion.version)
        )
    )


@router.post(
    "/api/plans/{plan_id}/template-bindings",
    response_model=PlanTemplateBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_template_binding(
    plan_id: int,
    payload: PlanTemplateBindingCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> PlanTemplateBinding:
    plan = ensure_plan(db, plan_id)
    ensure_exists(db, AnalysisTemplate, payload.template_id, "Template not found")
    before = plan_snapshot(plan)
    binding = PlanTemplateBinding(
        plan_id=plan_id,
        template_id=payload.template_id,
        experiment_no=payload.experiment_no,
        tube_no=payload.tube_no,
        config=payload.config,
        sort_order=payload.sort_order,
    )
    db.add(binding)
    plan.current_version += 1
    db.commit()
    db.refresh(binding)
    db.refresh(plan)
    version = create_plan_version(db, plan, payload.change_note, current_user.id)
    write_audit(db, request, current_user, "plan.template_binding.create", binding.id, before, plan_snapshot(plan))
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return binding


@router.post(
    "/api/plans/{plan_id}/cell-labels",
    response_model=CellLabelNodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cell_label(
    plan_id: int,
    payload: CellLabelNodeCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> CellLabelNode:
    plan = ensure_plan(db, plan_id)
    if payload.parent_node_id is not None:
        ensure_plan_child(db, CellLabelNode, plan_id, payload.parent_node_id, "Parent cell label not found")
    before = plan_snapshot(plan)
    node = CellLabelNode(
        plan_id=plan_id,
        parent_node_id=payload.parent_node_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
    )
    db.add(node)
    plan.current_version += 1
    db.commit()
    db.refresh(node)
    db.refresh(plan)
    version = create_plan_version(db, plan, payload.change_note, current_user.id)
    write_audit(db, request, current_user, "plan.cell_label.create", node.id, before, plan_snapshot(plan))
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return node


@router.post(
    "/api/plans/{plan_id}/marker-thresholds",
    response_model=MarkerThresholdResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_marker_threshold(
    plan_id: int,
    payload: MarkerThresholdCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_plans)],
    db: Annotated[Session, Depends(get_db)],
) -> MarkerThreshold:
    plan = ensure_plan(db, plan_id)
    if payload.label_node_id is not None:
        ensure_plan_child(db, CellLabelNode, plan_id, payload.label_node_id, "Cell label not found")
    before = plan_snapshot(plan)
    threshold = MarkerThreshold(
        plan_id=plan_id,
        label_node_id=payload.label_node_id,
        marker=payload.marker,
        channel_name=payload.channel_name,
        threshold_type=payload.threshold_type,
        threshold_value=payload.threshold_value,
        config=payload.config,
    )
    db.add(threshold)
    plan.current_version += 1
    db.commit()
    db.refresh(threshold)
    db.refresh(plan)
    version = create_plan_version(db, plan, payload.change_note, current_user.id)
    write_audit(db, request, current_user, "plan.marker_threshold.create", threshold.id, before, plan_snapshot(plan))
    write_audit(db, request, current_user, "plan.version.create", version.id, None, version_snapshot(version))
    return threshold


def ensure_plan(db: Session, plan_id: int) -> AnalysisPlan:
    plan = db.get(AnalysisPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


def ensure_exists(db: Session, model: type[Any], item_id: int, message: str) -> Any:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=message)
    return item


def ensure_plan_child(db: Session, model: type[Any], plan_id: int, item_id: int, message: str) -> Any:
    item = ensure_exists(db, model, item_id, message)
    if item.plan_id != plan_id:
        raise HTTPException(status_code=404, detail=message)
    return item


def plan_snapshot(plan: AnalysisPlan) -> dict[str, Any]:
    return AnalysisPlanResponse.model_validate(plan).model_dump(mode="json")


def version_snapshot(version: AnalysisPlanVersion) -> dict[str, Any]:
    return AnalysisPlanVersionResponse.model_validate(version).model_dump(mode="json")


def create_plan_version(
    db: Session,
    plan: AnalysisPlan,
    change_note: str,
    created_by: int,
) -> AnalysisPlanVersion:
    version = AnalysisPlanVersion(
        plan_id=plan.id,
        version=plan.current_version,
        snapshot_json=plan_snapshot(plan),
        change_note=change_note,
        created_by=created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def clone_template_bindings(source: AnalysisPlan, clone: AnalysisPlan) -> None:
    clone.template_bindings.extend(
        PlanTemplateBinding(
            template_id=binding.template_id,
            experiment_no=binding.experiment_no,
            tube_no=binding.tube_no,
            config=binding.config,
            sort_order=binding.sort_order,
        )
        for binding in source.template_bindings
    )


def clone_cell_label_nodes(source: AnalysisPlan, clone: AnalysisPlan, db: Session) -> dict[int, int]:
    label_map: dict[int, int] = {}
    for node in source.cell_label_nodes:
        cloned_node = CellLabelNode(
            code=node.code,
            name=node.name,
            description=node.description,
            sort_order=node.sort_order,
        )
        clone.cell_label_nodes.append(cloned_node)
        db.flush()
        label_map[node.id] = cloned_node.id
    for node in source.cell_label_nodes:
        if node.parent_node_id is not None:
            cloned_node_id = label_map[node.id]
            parent_node_id = label_map.get(node.parent_node_id)
            if parent_node_id is not None:
                db.get(CellLabelNode, cloned_node_id).parent_node_id = parent_node_id
    return label_map


def clone_marker_thresholds(source: AnalysisPlan, clone: AnalysisPlan, label_map: dict[int, int]) -> None:
    clone.marker_thresholds.extend(
        MarkerThreshold(
            label_node_id=label_map.get(threshold.label_node_id) if threshold.label_node_id else None,
            marker=threshold.marker,
            channel_name=threshold.channel_name,
            threshold_type=threshold.threshold_type,
            threshold_value=threshold.threshold_value,
            config=threshold.config,
        )
        for threshold in source.marker_thresholds
    )


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
        resource_type="analysis_plan",
        resource_id=str(resource_id),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        operation_result="success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
