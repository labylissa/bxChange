import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.workers.celery_app import celery_app


def _make_session():
    """Create a fresh engine + session for each task invocation (NullPool avoids cross-loop issues)."""
    from app.core.config import settings
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False), engine


@celery_app.task(name="execute_scheduled_job")
def execute_scheduled_job(scheduled_job_id: str) -> dict:
    async def _run() -> dict:
        from app.models.connector import Connector
        from app.models.scheduled_job import ScheduledJob
        from app.schemas.scheduled_job import compute_next_run
        from app.services import execution_service

        Session, engine = _make_session()
        try:
            async with Session() as db:
                job = (await db.execute(
                    select(ScheduledJob).where(ScheduledJob.id == uuid.UUID(scheduled_job_id))
                )).scalar_one_or_none()

                if not job or not job.is_active:
                    return {"status": "skipped", "reason": "job inactive or not found"}

                connector = (await db.execute(
                    select(Connector).where(Connector.id == job.connector_id)
                )).scalar_one_or_none()

                if not connector or connector.status == "disabled":
                    return {"status": "skipped", "reason": "connector disabled or not found"}

                exec_read = await execution_service.execute_connector(
                    connector_id=job.connector_id,
                    tenant_id=job.tenant_id,
                    params=job.input_params or {},
                    body=None,
                    transform_override=None,
                    triggered_by="scheduled",
                    db=db,
                )

                job.last_run_at = datetime.utcnow()
                job.next_run_at = compute_next_run(job.schedule_type, job.cron_expression, job.interval_seconds)
                await db.commit()

                return {"status": "ok", "execution_id": str(exec_read.id)}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name="poll_scheduled_jobs")
def poll_scheduled_jobs() -> dict:
    async def _poll() -> dict:
        from app.models.scheduled_job import ScheduledJob
        from app.schemas.scheduled_job import compute_next_run

        now = datetime.utcnow()
        dispatched: list[str] = []

        Session, engine = _make_session()
        try:
            async with Session() as db:
                jobs = (await db.execute(
                    select(ScheduledJob).where(
                        ScheduledJob.is_active.is_(True),
                        ScheduledJob.next_run_at <= now,
                    )
                )).scalars().all()

                for job in jobs:
                    execute_scheduled_job.delay(str(job.id))
                    dispatched.append(str(job.id))
                    job.next_run_at = compute_next_run(job.schedule_type, job.cron_expression, job.interval_seconds)

                await db.commit()
        finally:
            await engine.dispose()

        return {"dispatched": len(dispatched), "job_ids": dispatched}

    return asyncio.run(_poll())
