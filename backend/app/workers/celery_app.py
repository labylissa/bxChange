from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "bxchange",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

celery_app.conf.beat_schedule = {
    "scheduler-ticker": {
        "task": "poll_scheduled_jobs",
        "schedule": 60.0,
    },
    "reset-monthly": {
        "task": "reset_monthly_executions",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
    },
    "check-license-expiry": {
        "task": "check_license_expiry",
        "schedule": crontab(hour=8, minute=0),
    },
}
