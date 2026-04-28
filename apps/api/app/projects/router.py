from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditLogService, actor_role_codes
from app.auth.dependencies import get_current_user, require_any_permission
from app.db.session import get_db
from app.projects.models import Channel, Experiment, MarkerMapping, Project, Sample, Tube
from app.projects.schemas import (
    ChannelCreate,
    ChannelResponse,
    ExperimentCreate,
    ExperimentResponse,
    MarkerMappingCreate,
    MarkerMappingResponse,
    ProjectCreate,
    ProjectResponse,
    SampleCreate,
    SampleResponse,
    TubeCreate,
    TubeResponse,
)
from app.uploads.models import DataFile
from app.users.models import User

router = APIRouter(tags=["metadata"])
write_metadata = require_any_permission({"upload:write", "admin:write"})


@router.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    write_audit(db, request, current_user, "project.create", "project", project.id, payload.model_dump())
    return project


@router.get("/api/projects", response_model=list[ProjectResponse])
def list_projects(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.id)))


@router.post("/api/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> Experiment:
    ensure_exists(db, Project, payload.project_id, "Project not found")
    experiment = Experiment(**payload.model_dump())
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    write_audit(db, request, current_user, "experiment.create", "experiment", experiment.id, payload.model_dump())
    return experiment


@router.get("/api/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Experiment:
    return ensure_exists(db, Experiment, experiment_id, "Experiment not found")


@router.post("/api/samples", response_model=SampleResponse, status_code=status.HTTP_201_CREATED)
def create_sample(
    payload: SampleCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> Sample:
    ensure_exists(db, Experiment, payload.experiment_id, "Experiment not found")
    sample = Sample(**payload.model_dump())
    db.add(sample)
    db.commit()
    db.refresh(sample)
    write_audit(db, request, current_user, "sample.create", "sample", sample.id, payload.model_dump())
    return sample


@router.post("/api/tubes", response_model=TubeResponse, status_code=status.HTTP_201_CREATED)
def create_tube(
    payload: TubeCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> Tube:
    ensure_exists(db, Sample, payload.sample_id, "Sample not found")
    tube_data = payload.model_dump(exclude={"data_file_ids"})
    tube = Tube(**tube_data)
    db.add(tube)
    db.flush()
    for data_file_id in payload.data_file_ids:
        data_file = ensure_exists(db, DataFile, data_file_id, "Data file not found")
        data_file.tube_id = tube.id
    db.commit()
    db.refresh(tube)
    write_audit(db, request, current_user, "tube.create", "tube", tube.id, payload.model_dump())
    return tube


@router.post(
    "/api/tubes/{tube_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    tube_id: int,
    payload: ChannelCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> Channel:
    ensure_exists(db, Tube, tube_id, "Tube not found")
    channel = Channel(tube_id=tube_id, **payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    write_audit(db, request, current_user, "channel.create", "channel", channel.id, {"tube_id": tube_id, **payload.model_dump()})
    return channel


@router.post(
    "/api/tubes/{tube_id}/marker-mappings",
    response_model=MarkerMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_marker_mapping(
    tube_id: int,
    payload: MarkerMappingCreate,
    request: Request,
    current_user: Annotated[User, Depends(write_metadata)],
    db: Annotated[Session, Depends(get_db)],
) -> MarkerMapping:
    ensure_exists(db, Tube, tube_id, "Tube not found")
    marker_mapping = MarkerMapping(tube_id=tube_id, **payload.model_dump())
    db.add(marker_mapping)
    db.commit()
    db.refresh(marker_mapping)
    write_audit(
        db,
        request,
        current_user,
        "marker_mapping.create",
        "marker_mapping",
        marker_mapping.id,
        {"tube_id": tube_id, **payload.model_dump()},
    )
    return marker_mapping


def ensure_exists(db: Session, model: type[Any], item_id: int, message: str) -> Any:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=message)
    return item


def write_audit(
    db: Session,
    request: Request,
    current_user: User,
    operation_type: str,
    resource_type: str,
    resource_id: int,
    snapshot: dict[str, Any],
) -> None:
    AuditLogService(db).create_log(
        actor_user_id=current_user.id,
        actor_role=actor_role_codes(current_user.roles),
        operation_type=operation_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_snapshot=None,
        after_snapshot=snapshot,
        operation_result="success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
