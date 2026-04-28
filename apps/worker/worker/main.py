from __future__ import annotations

from celery import Celery

from worker.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "flow_cytometry_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.analysis_pipeline",
        "worker.tasks.export_pipeline",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
)

