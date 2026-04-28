from __future__ import annotations

from worker.settings import get_settings

try:
    from celery import Celery
except ModuleNotFoundError:
    Celery = None


class _CeleryFallback:
    def __init__(self) -> None:
        self.conf: dict[str, object] = {}

    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


settings = get_settings()

if Celery is None:
    celery_app = _CeleryFallback()
else:
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
