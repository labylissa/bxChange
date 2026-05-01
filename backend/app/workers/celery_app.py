from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bxchange",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

celery_app.conf.beat_schedule = {
    "scheduler-ticker": {
        "task": "poll_scheduled_jobs",
        "schedule": 60.0,
    }
}
