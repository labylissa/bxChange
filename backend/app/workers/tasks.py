import asyncio
import json
import logging
import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.workers.celery_app import celery_app

_log = logging.getLogger(__name__)


def _make_session():
    """Create a fresh engine + session for each task invocation (NullPool avoids cross-loop issues)."""
    from app.core.config import settings
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False), engine


@celery_app.task(name="execute_scheduled_job")
def execute_scheduled_job(scheduled_job_id: str) -> dict:
    async def _run() -> dict:
        from app.models.connector import Connector
        from app.models.pipeline import Pipeline
        from app.models.scheduled_job import ScheduledJob
        from app.models.tenant import Tenant
        from app.schemas.scheduled_job import compute_next_run
        from app.services import execution_service
        from app.services.pipeline_engine import PipelineEngine

        Session, engine = _make_session()
        try:
            async with Session() as db:
                job = (await db.execute(
                    select(ScheduledJob).where(ScheduledJob.id == uuid.UUID(scheduled_job_id))
                )).scalar_one_or_none()

                if not job or not job.is_active:
                    return {"status": "skipped", "reason": "job inactive or not found"}

                job.last_run_at = datetime.utcnow()
                job.next_run_at = compute_next_run(job.schedule_type, job.cron_expression, job.interval_seconds)

                if job.pipeline_id:
                    pipeline = (await db.execute(
                        select(Pipeline).where(Pipeline.id == job.pipeline_id)
                    )).scalar_one_or_none()
                    if not pipeline or not pipeline.is_active:
                        return {"status": "skipped", "reason": "pipeline disabled or not found"}

                    tenant = (await db.execute(
                        select(Tenant).where(Tenant.id == job.tenant_id)
                    )).scalar_one_or_none()

                    pe_engine = PipelineEngine()
                    result = await pe_engine.execute(
                        pipeline=pipeline,
                        input_params=job.input_params or {},
                        tenant=tenant,
                        db=db,
                        triggered_by="scheduled",
                    )
                    await db.commit()
                    return {"status": result.status, "pipeline_id": str(job.pipeline_id)}

                else:
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


@celery_app.task(name="reset_monthly_executions")
def reset_monthly_executions() -> dict:
    async def _run() -> dict:
        from app.models.tenant import Tenant

        Session, engine = _make_session()
        try:
            async with Session() as db:
                tenants = (await db.execute(
                    select(Tenant).where(Tenant.license_status.in_(["active", "trial"]))
                )).scalars().all()
                for tenant in tenants:
                    tenant.executions_used = 0
                await db.commit()
                _log.info("Monthly reset: %d tenants reset", len(tenants))
                return {"reset_count": len(tenants)}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name="check_license_expiry")
def check_license_expiry() -> dict:
    async def _run() -> dict:
        from datetime import timedelta

        from app.models.license import License
        from app.models.tenant import Tenant

        Session, engine = _make_session()
        expired_count = 0
        warning_count = 0
        now = datetime.utcnow()

        try:
            async with Session() as db:
                # Auto-expire licenses past contract_end
                tenants = (await db.execute(select(Tenant))).scalars().all()
                for tenant in tenants:
                    if (
                        tenant.license_status in ("active", "trial")
                        and tenant.contract_end
                        and tenant.contract_end < now
                    ):
                        tenant.license_status = "expired"
                        expired_count += 1
                        _log.warning(
                            "License expired: tenant=%s contract_end=%s",
                            tenant.name,
                            tenant.contract_end,
                        )

                    # Warn when expiry is within 30 days
                    if (
                        tenant.license_status == "active"
                        and tenant.contract_end
                        and now < tenant.contract_end <= now + timedelta(days=30)
                    ):
                        days = (tenant.contract_end - now).days
                        _log.warning(
                            "License expiring soon: tenant=%s days_remaining=%d",
                            tenant.name,
                            days,
                        )
                        warning_count += 1

                await db.commit()
        finally:
            await engine.dispose()

        return {"expired": expired_count, "warnings": warning_count}

    return asyncio.run(_run())


class _NeedsRetry(Exception):
    def __init__(self, cause: Exception) -> None:
        self.cause = cause


@celery_app.task(name="dispatch_webhook", bind=True, max_retries=3, default_retry_delay=60)
def dispatch_webhook(self, webhook_id: str, payload: dict, signature: str) -> dict:
    async def _run() -> dict:
        from app.models.webhook_endpoint import WebhookEndpoint

        body_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()

        Session, engine = _make_session()
        try:
            async with Session() as db:
                wh = (await db.execute(
                    select(WebhookEndpoint).where(
                        WebhookEndpoint.id == uuid.UUID(webhook_id),
                        WebhookEndpoint.is_active.is_(True),
                    )
                )).scalar_one_or_none()

                if not wh:
                    return {"webhook_id": webhook_id, "status_code": None, "ok": False, "reason": "inactive or not found"}

                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            wh.url,
                            content=body_bytes,
                            headers={
                                "Content-Type": "application/json",
                                "X-bxChange-Signature": signature,
                                "User-Agent": "bxChange-Webhooks/1.0",
                            },
                        )

                    wh.last_triggered_at = datetime.utcnow()
                    wh.last_status_code = resp.status_code
                    await db.commit()

                    if resp.status_code >= 500:
                        raise _NeedsRetry(Exception(f"HTTP {resp.status_code} from webhook {webhook_id}"))

                    if resp.status_code >= 400:
                        _log.warning("Webhook %s returned 4xx: %s — no retry", webhook_id, resp.status_code)

                    return {"webhook_id": webhook_id, "status_code": resp.status_code, "ok": resp.status_code < 400}

                except httpx.TimeoutException as exc:
                    raise _NeedsRetry(exc)

        finally:
            await engine.dispose()

    try:
        return asyncio.run(_run())
    except _NeedsRetry as exc:
        raise self.retry(exc=exc.cause, countdown=60 * (2 ** self.request.retries))
