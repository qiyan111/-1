from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis.models import (
    AnalysisBatch,
    AnalysisJob,
    AnalysisResult,
    AnalysisStatus,
    ResultConfidenceScore,
    ResultGate,
    ResultStatistic,
)
from app.auth.security import hash_password
from app.db.base import Base
import app.plans.models  # noqa: F401
import app.projects.models  # noqa: F401
from app.templates.models import AnalysisTemplate, TemplateGate, TemplateStatistic
from app.uploads.models import DataFile, UploadBatch
from app.users.models import Role, User

WORKER_PATH = Path(__file__).resolve().parents[3] / "worker"
if str(WORKER_PATH) not in sys.path:
    sys.path.insert(0, str(WORKER_PATH))

from worker.tasks.analysis_pipeline import run_analysis_job  # noqa: E402


def build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def seed_user(db: Session) -> User:
    role = Role(code="analyst", name="Analyst", description="Analyst")
    user = User(
        email="analyst@example.com",
        username="analyst",
        hashed_password=hash_password("AnalystPass123!"),
        roles=[role],
    )
    db.add(user)
    db.flush()
    return user


def seed_template(db: Session, user: User) -> AnalysisTemplate:
    template = AnalysisTemplate(
        name="CSV Template",
        project_code="FLOW",
        created_by_user_id=user.id,
        gates=[
            TemplateGate(
                gate_key="LYM",
                name="Lymphocytes",
                gate_type="rectangle",
                definition={
                    "x_channel": "FSC-A",
                    "y_channel": "SSC-A",
                    "x_min": 0.0,
                    "x_max": 3.0,
                    "y_min": 0.0,
                    "y_max": 3.0,
                },
            )
        ],
        statistics=[
            TemplateStatistic(
                name="LYM % total",
                rule_type="percent_total",
                config={"gate": "LYM"},
            )
        ],
    )
    db.add(template)
    db.flush()
    return template


def seed_job(
    session_factory: sessionmaker[Session],
    csv_path: Path,
    *,
    with_template: bool = True,
) -> int:
    with session_factory() as db:
        user = seed_user(db)
        template = seed_template(db, user) if with_template else None
        upload_batch = UploadBatch(uploaded_by_user_id=user.id, status="completed")
        db.add(upload_batch)
        db.flush()
        data_file = DataFile(
            upload_batch_id=upload_batch.id,
            uploaded_by_user_id=user.id,
            original_filename=csv_path.name,
            file_extension=".csv",
            content_type="text/csv",
            object_bucket="local",
            object_key=str(csv_path),
            file_size=csv_path.stat().st_size if csv_path.exists() else 0,
            sha256="0" * 64,
        )
        db.add(data_file)
        db.flush()
        analysis_batch = AnalysisBatch(
            upload_batch_id=upload_batch.id,
            template_id=template.id if template else None,
            requested_by_user_id=user.id,
            status=AnalysisStatus.QUEUED.value,
            total_jobs=1,
        )
        db.add(analysis_batch)
        db.flush()
        job = AnalysisJob(
            analysis_batch_id=analysis_batch.id,
            data_file_id=data_file.id,
            status=AnalysisStatus.QUEUED.value,
            logs=[],
        )
        db.add(job)
        db.commit()
        return job.id


def write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    path.write_text(
        "FSC-A,SSC-A,CD45\n"
        "1,1,10\n"
        "2,2,20\n"
        "5,5,30\n",
        encoding="utf-8",
    )
    return path


def test_analysis_pipeline_success_saves_results(tmp_path: Path) -> None:
    session_factory = build_session_factory()
    job_id = seed_job(session_factory, write_csv(tmp_path))

    output = run_analysis_job(job_id, session_factory=session_factory)

    assert output["status"] == AnalysisStatus.COMPLETED.value
    with session_factory() as db:
        job = db.get(AnalysisJob, job_id)
        result = db.scalar(select(AnalysisResult).where(AnalysisResult.analysis_job_id == job_id))
        gate = db.scalar(select(ResultGate))
        statistic = db.scalar(select(ResultStatistic))
        confidence = db.scalar(select(ResultConfidenceScore))

        assert job is not None
        assert job.status == AnalysisStatus.COMPLETED.value
        assert job.batch.status == AnalysisStatus.COMPLETED.value
        assert result is not None
        assert result.status == AnalysisStatus.COMPLETED.value
        assert gate is not None
        assert gate.gate_key == "LYM"
        assert gate.event_count == 2
        assert statistic is not None
        assert statistic.name == "LYM % total"
        assert statistic.value["value"] == (2 / 3) * 100.0
        assert confidence is not None
        assert confidence.level == "green"


def test_analysis_pipeline_failure_updates_job(tmp_path: Path) -> None:
    session_factory = build_session_factory()
    missing_path = tmp_path / "missing.csv"
    job_id = seed_job(session_factory, missing_path, with_template=False)

    output = run_analysis_job(job_id, session_factory=session_factory)

    assert output["status"] == AnalysisStatus.FAILED.value
    with session_factory() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        assert job.status == AnalysisStatus.FAILED.value
        assert job.batch.status == AnalysisStatus.FAILED.value
        assert job.error_message
        assert job.logs[-1]["level"] == "ERROR"
        assert db.scalar(select(AnalysisResult)) is None


def test_analysis_pipeline_autogating_without_template(tmp_path: Path) -> None:
    session_factory = build_session_factory()
    job_id = seed_job(session_factory, write_csv(tmp_path), with_template=False)

    output = run_analysis_job(job_id, session_factory=session_factory)

    assert output["status"] == AnalysisStatus.COMPLETED.value
    with session_factory() as db:
        gate = db.scalar(select(ResultGate))
        statistic = db.scalar(select(ResultStatistic))
        confidence = db.scalar(select(ResultConfidenceScore))

        assert gate is not None
        assert gate.gate_key == "AUTO"
        assert gate.gate_type in {"ellipse", "linear"}
        assert statistic is not None
        assert statistic.name == "AUTO event count"
        assert confidence is not None
        assert confidence.metadata_json["algorithm_name"] in {"kmeans", "density_valley_threshold"}
