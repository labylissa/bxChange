import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_developer_or_above
from app.models.connector import Connector
from app.models.scheduled_job import ScheduledJob
from app.models.user import User
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobRead,
    ScheduledJobUpdate,
    compute_next_run,
)

router = APIRouter(prefix="/scheduled-jobs", tags=["scheduled-jobs"])


def _to_read(job: ScheduledJob, connector_name: str | None) -> ScheduledJobRead:
    return ScheduledJobRead.model_validate(job).model_copy(update={"connector_name": connector_name})


async def _get_job(job_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> ScheduledJob:
    job = (await db.execute(
        select(ScheduledJob).where(
            ScheduledJob.id == job_id,
            ScheduledJob.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")
    return job


async def _connector_name(connector_id: uuid.UUID, db: AsyncSession) -> str | None:
    c = (await db.execute(select(Connector).where(Connector.id == connector_id))).scalar_one_or_none()
    return c.name if c else None


@router.get(
    "",
    response_model=list[ScheduledJobRead],
    summary="Lister les jobs planifiés",
)
async def list_scheduled_jobs(
    connector_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledJobRead]:
    q = select(ScheduledJob).where(ScheduledJob.tenant_id == current_user.tenant_id)
    if connector_id:
        q = q.where(ScheduledJob.connector_id == connector_id)
    jobs = (await db.execute(q)).scalars().all()
    result = []
    for job in jobs:
        name = await _connector_name(job.connector_id, db)
        result.append(_to_read(job, name))
    return result


@router.post(
    "",
    response_model=ScheduledJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un job planifié",
)
async def create_scheduled_job(
    payload: ScheduledJobCreate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    connector = (await db.execute(
        select(Connector).where(
            Connector.id == payload.connector_id,
            Connector.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    job = ScheduledJob(
        connector_id=payload.connector_id,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        schedule_type=payload.schedule_type,
        cron_expression=payload.cron_expression,
        interval_seconds=payload.interval_seconds,
        input_params=payload.input_params,
        next_run_at=compute_next_run(payload.schedule_type, payload.cron_expression, payload.interval_seconds),
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _to_read(job, connector.name)


@router.get(
    "/{job_id}",
    response_model=ScheduledJobRead,
    summary="Détail d'un job planifié",
)
async def get_scheduled_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    job = await _get_job(job_id, current_user.tenant_id, db)
    return _to_read(job, await _connector_name(job.connector_id, db))


@router.put(
    "/{job_id}",
    response_model=ScheduledJobRead,
    summary="Modifier un job planifié",
)
async def update_scheduled_job(
    job_id: uuid.UUID,
    payload: ScheduledJobUpdate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    job = await _get_job(job_id, current_user.tenant_id, db)

    if payload.name is not None:
        job.name = payload.name
    if payload.schedule_type is not None:
        job.schedule_type = payload.schedule_type
    if payload.cron_expression is not None:
        job.cron_expression = payload.cron_expression
    if payload.interval_seconds is not None:
        job.interval_seconds = payload.interval_seconds
    if payload.input_params is not None:
        job.input_params = payload.input_params
    if payload.is_active is not None:
        job.is_active = payload.is_active

    # Recalculate next_run_at if schedule changed
    if payload.schedule_type is not None or payload.cron_expression is not None or payload.interval_seconds is not None:
        job.next_run_at = compute_next_run(job.schedule_type, job.cron_expression, job.interval_seconds)

    await db.commit()
    await db.refresh(job)
    return _to_read(job, await _connector_name(job.connector_id, db))


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un job planifié",
)
async def delete_scheduled_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    job = await _get_job(job_id, current_user.tenant_id, db)
    await db.delete(job)
    await db.commit()


@router.post(
    "/{job_id}/toggle",
    response_model=ScheduledJobRead,
    summary="Activer / désactiver un job planifié",
)
async def toggle_scheduled_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    job = await _get_job(job_id, current_user.tenant_id, db)
    job.is_active = not job.is_active
    if job.is_active and job.next_run_at is None:
        job.next_run_at = compute_next_run(job.schedule_type, job.cron_expression, job.interval_seconds)
    await db.commit()
    await db.refresh(job)
    return _to_read(job, await _connector_name(job.connector_id, db))


@router.post(
    "/{job_id}/run-now",
    summary="Déclencher manuellement un job planifié",
)
async def run_now(
    job_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await _get_job(job_id, current_user.tenant_id, db)
    from app.workers.tasks import execute_scheduled_job
    execute_scheduled_job.delay(str(job.id))
    return {"dispatched": True, "job_id": str(job.id)}
