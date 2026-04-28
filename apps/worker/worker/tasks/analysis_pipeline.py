from __future__ import annotations

from worker.main import celery_app


@celery_app.task(name="analysis.run_pipeline")
def run_analysis_pipeline(batch_id: str) -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "status": "not_implemented",
    }

