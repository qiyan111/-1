from __future__ import annotations

from worker.main import celery_app


@celery_app.task(name="exports.run_pipeline")
def run_export_pipeline(task_id: str) -> dict[str, str]:
    return {
        "task_id": task_id,
        "status": "not_implemented",
    }

