from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.analysis.models import (
    AnalysisJob,
    AnalysisResult,
    AnalysisStatus,
    ResultConfidenceScore,
    ResultGate,
    ResultStatistic,
)
from app.analysis_engine import get_parser
from app.analysis_engine.autogating import DensityValleyThresholdGate, KMeansAutoGate
from app.analysis_engine.autogating.base import ConfidenceScore
from app.analysis_engine.gating import evaluate_gate, evaluate_logic_gate
from app.analysis_engine.statistics import evaluate_statistics
from app.db.session import get_sessionmaker
from app.plans.models import MarkerThreshold
from app.templates.models import AnalysisTemplate
from app.uploads.models import DataFile
from worker.main import celery_app


@celery_app.task(name="analysis.run_pipeline")
def run_analysis_pipeline(job_id: int) -> dict[str, Any]:
    return run_analysis_job(job_id)


def run_analysis_job(
    job_id: int,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> dict[str, Any]:
    factory = session_factory or get_sessionmaker()
    with factory() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f"Analysis job {job_id} not found")
        return _run_analysis_job(db, job)


def _run_analysis_job(db: Session, job: AnalysisJob) -> dict[str, Any]:
    try:
        _set_job_status(db, job, AnalysisStatus.RUNNING, "Analysis pipeline started")
        data_file = db.get(DataFile, job.data_file_id)
        if data_file is None:
            raise ValueError(f"Data file {job.data_file_id} not found")
        file_path = _resolve_data_file_path(data_file)

        parser = get_parser(file_path)
        parsed = parser.parse(file_path)
        _append_job_log(job, "INFO", "File parsed")
        _append_job_log(job, "INFO", "Compensation placeholder applied")
        _append_job_log(job, "INFO", "Coordinate transform placeholder applied")

        template = _template_for_job(db, job)
        gate_outputs, confidence, algorithm_metadata = _execute_gates(
            events=parsed.events,
            channels=[channel.name for channel in parsed.channels],
            template=template,
        )
        statistic_definitions = _statistic_definitions(template, gate_outputs)
        marker_thresholds = _marker_thresholds_for_job(job)
        statistic_results = evaluate_statistics(
            parsed.events,
            [channel.name for channel in parsed.channels],
            {"TOTAL": [True for _ in parsed.events], **{key: output["mask"] for key, output in gate_outputs.items()}},
            statistic_definitions,
            marker_thresholds,
        )

        result = _save_result(
            db=db,
            job=job,
            gate_outputs=gate_outputs,
            statistic_results=statistic_results,
            confidence=confidence,
            algorithm_metadata=algorithm_metadata,
            summary={
                "metadata": {
                    "format": parsed.metadata.format,
                    "file_name": parsed.metadata.file_name,
                    "row_count": parsed.metadata.row_count,
                    "channel_count": parsed.metadata.channel_count,
                },
                "channels": [channel.name for channel in parsed.channels],
            },
        )
        _set_job_status(db, job, AnalysisStatus.COMPLETED, "Analysis pipeline completed")
        _refresh_batch_status(job)
        db.commit()
        return {"job_id": job.id, "result_id": result.id, "status": AnalysisStatus.COMPLETED.value}
    except Exception as exc:
        db.rollback()
        failed_job = db.get(AnalysisJob, job.id)
        if failed_job is not None:
            failed_job.status = AnalysisStatus.FAILED.value
            failed_job.error_message = str(exc)
            _append_job_log(failed_job, "ERROR", str(exc))
            _refresh_batch_status(failed_job)
            db.commit()
        return {"job_id": job.id, "status": AnalysisStatus.FAILED.value, "error": str(exc)}


def _execute_gates(
    *,
    events: list[list[float]],
    channels: list[str],
    template: AnalysisTemplate | None,
) -> tuple[dict[str, dict[str, Any]], ConfidenceScore, dict[str, Any] | None]:
    if template is not None and template.gates:
        return _execute_template_gates(events, channels, template), ConfidenceScore(
            level="green",
            score=1.0,
            reasons=["Template gates applied"],
        ), {"mode": "template"}
    return _execute_auto_gate(events, channels)


def _execute_template_gates(
    events: list[list[float]],
    channels: list[str],
    template: AnalysisTemplate,
) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for template_gate in template.gates:
        parent_mask = outputs[template_gate.parent_gate_key]["mask"] if template_gate.parent_gate_key else None
        definition = {**template_gate.definition, "type": template_gate.gate_type}
        evaluation = evaluate_gate(events, channels, definition, parent_mask=parent_mask)
        outputs[template_gate.gate_key] = {
            "gate_key": template_gate.gate_key,
            "gate_name": template_gate.name,
            "gate_type": template_gate.gate_type,
            "definition": definition,
            "mask": evaluation.mask,
            "event_count": evaluation.event_count,
            "parent_gate_key": template_gate.parent_gate_key,
            "parent_event_count": sum(parent_mask) if parent_mask is not None else len(events),
        }
    for logic_gate in template.logic_gates:
        expression = logic_gate.definition if logic_gate.definition is not None else logic_gate.expression
        evaluation = evaluate_logic_gate(expression, {key: output["mask"] for key, output in outputs.items()})
        outputs[logic_gate.name] = {
            "gate_key": logic_gate.name,
            "gate_name": logic_gate.name,
            "gate_type": "logic",
            "definition": {"expression": expression},
            "mask": evaluation.mask,
            "event_count": evaluation.event_count,
            "parent_gate_key": None,
            "parent_event_count": len(events),
        }
    return outputs


def _execute_auto_gate(
    events: list[list[float]],
    channels: list[str],
) -> tuple[dict[str, dict[str, Any]], ConfidenceScore, dict[str, Any]]:
    if len(channels) >= 2:
        algorithm = KMeansAutoGate().fit(
            events,
            channels,
            {"x_channel": channels[0], "y_channel": channels[1], "k": 2, "target_cluster": "largest"},
        )
    else:
        algorithm = DensityValleyThresholdGate().fit(
            events,
            channels,
            {"channel": channels[0], "bins": 8, "direction": "above"},
        )
    gate_definition = algorithm.predict_gate()
    evaluation = evaluate_gate(events, channels, gate_definition)
    return {
        "AUTO": {
            "gate_key": "AUTO",
            "gate_name": str(gate_definition.get("name", "Auto Gate")),
            "gate_type": str(gate_definition["type"]),
            "definition": gate_definition,
            "mask": evaluation.mask,
            "event_count": evaluation.event_count,
            "parent_gate_key": None,
            "parent_event_count": len(events),
        }
    }, algorithm.confidence(), algorithm.metadata()


def _save_result(
    *,
    db: Session,
    job: AnalysisJob,
    gate_outputs: dict[str, dict[str, Any]],
    statistic_results: list[Any],
    confidence: ConfidenceScore,
    algorithm_metadata: dict[str, Any] | None,
    summary: dict[str, Any],
) -> AnalysisResult:
    if job.result is not None:
        db.delete(job.result)
        db.flush()
    result = AnalysisResult(
        analysis_batch_id=job.analysis_batch_id,
        analysis_job_id=job.id,
        data_file_id=job.data_file_id,
        status=AnalysisStatus.COMPLETED.value,
        summary=summary,
    )
    db.add(result)
    db.flush()
    for output in gate_outputs.values():
        db.add(
            ResultGate(
                analysis_result_id=result.id,
                gate_key=output["gate_key"],
                gate_name=output["gate_name"],
                gate_type=output["gate_type"],
                definition=output["definition"],
                event_count=output["event_count"],
                parent_event_count=output["parent_event_count"],
                mask=output["mask"],
            )
        )
    for statistic_result in statistic_results:
        db.add(
            ResultStatistic(
                analysis_result_id=result.id,
                name=statistic_result.name,
                statistic_type=statistic_result.statistic_type,
                value={"value": statistic_result.value},
                unit=statistic_result.unit,
                metadata_json=statistic_result.metadata,
            )
        )
    db.add(
        ResultConfidenceScore(
            analysis_result_id=result.id,
            level=confidence.level,
            score=confidence.score,
            reason="; ".join(confidence.reasons),
            metadata_json=algorithm_metadata,
        )
    )
    db.flush()
    return result


def _statistic_definitions(template: AnalysisTemplate | None, gate_outputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if template is not None and template.statistics:
        return [
            {"name": statistic.name, "type": statistic.rule_type, **(statistic.config or {})}
            for statistic in template.statistics
        ]
    return [
        {"name": f"{gate_key} event count", "type": "event_count", "gate": gate_key}
        for gate_key in gate_outputs
    ]


def _marker_thresholds_for_job(job: AnalysisJob) -> list[dict[str, Any]]:
    plan = job.batch.plan if hasattr(job.batch, "plan") else None
    if plan is None:
        return []
    thresholds: list[dict[str, Any]] = []
    for threshold in plan.marker_thresholds:
        if isinstance(threshold, MarkerThreshold):
            thresholds.append(
                {
                    "marker": threshold.marker,
                    "channel": threshold.channel_name,
                    "threshold_type": threshold.threshold_type,
                    "threshold_value": threshold.threshold_value,
                }
            )
    return thresholds


def _template_for_job(db: Session, job: AnalysisJob) -> AnalysisTemplate | None:
    if job.batch.template_id is None:
        return None
    return db.get(AnalysisTemplate, job.batch.template_id)


def _resolve_data_file_path(data_file: DataFile) -> Path:
    object_path = Path(data_file.object_key)
    if object_path.exists():
        return object_path
    raise FileNotFoundError(
        "Data file object is not available on local filesystem; object storage download is not implemented yet"
    )


def _set_job_status(db: Session, job: AnalysisJob, status: AnalysisStatus, message: str) -> None:
    job.status = status.value
    _append_job_log(job, "INFO", message)
    _refresh_batch_status(job)
    db.commit()
    db.refresh(job)


def _append_job_log(job: AnalysisJob, level: str, message: str) -> None:
    job.logs = [
        *(job.logs or []),
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        },
    ]


def _refresh_batch_status(job: AnalysisJob) -> None:
    batch = job.batch
    batch.total_jobs = len(batch.jobs)
    batch.completed_jobs = len([item for item in batch.jobs if item.status == AnalysisStatus.COMPLETED.value])
    batch.failed_jobs = len([item for item in batch.jobs if item.status == AnalysisStatus.FAILED.value])
    if batch.total_jobs and batch.completed_jobs == batch.total_jobs:
        batch.status = AnalysisStatus.COMPLETED.value
    elif batch.failed_jobs:
        batch.status = AnalysisStatus.FAILED.value
    elif any(item.status == AnalysisStatus.RUNNING.value for item in batch.jobs):
        batch.status = AnalysisStatus.RUNNING.value
