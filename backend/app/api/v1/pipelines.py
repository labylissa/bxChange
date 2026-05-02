import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_execute_auth
from app.models.connector import Connector
from app.models.pipeline import Pipeline, PipelineExecution, PipelineStep
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineExecuteRequest,
    PipelineExecutionRead,
    PipelineRead,
    PipelineStepRead,
    PipelineUpdate,
)
from app.services.execution_service import (
    LicenseExpiredError,
    LicenseSuspendedError,
    QuotaExceededError,
)
from app.services.pipeline_engine import PipelineEngine

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


async def _build_pipeline_read(pipeline: Pipeline, db: AsyncSession) -> PipelineRead:
    steps_result = await db.execute(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline.id)
    )
    steps = list(steps_result.scalars().all())

    # Load connector names/types
    step_reads = []
    for step in sorted(steps, key=lambda s: s.step_order):
        connector = (await db.execute(
            select(Connector).where(Connector.id == step.connector_id)
        )).scalar_one_or_none()
        step_reads.append(PipelineStepRead(
            id=step.id,
            connector_id=step.connector_id,
            step_order=step.step_order,
            name=step.name,
            execution_mode=step.execution_mode,
            params_template=step.params_template or {},
            condition=step.condition,
            on_error=step.on_error,
            timeout_seconds=step.timeout_seconds,
            connector_name=connector.name if connector else "Unknown",
            connector_type=connector.type if connector else "unknown",
        ))

    exec_count = (await db.execute(
        select(func.count(PipelineExecution.id)).where(PipelineExecution.pipeline_id == pipeline.id)
    )).scalar_one()

    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        description=pipeline.description,
        is_active=pipeline.is_active,
        merge_strategy=pipeline.merge_strategy,
        output_transform=pipeline.output_transform,
        steps=step_reads,
        created_at=pipeline.created_at,
        executions_count=exec_count,
    )


async def _get_pipeline(
    pipeline_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Pipeline:
    pipeline = (await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


@router.get("", response_model=list[PipelineRead], summary="Lister les pipelines")
async def list_pipelines(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PipelineRead]:
    pipelines = (await db.execute(
        select(Pipeline).where(Pipeline.tenant_id == current_user.tenant_id)
    )).scalars().all()
    return [await _build_pipeline_read(p, db) for p in pipelines]


@router.post("", response_model=PipelineRead, status_code=status.HTTP_201_CREATED,
             summary="Créer un pipeline")
async def create_pipeline(
    payload: PipelineCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineRead:
    # Validate connector ownership
    for step_data in payload.steps:
        connector = (await db.execute(
            select(Connector).where(
                Connector.id == step_data.connector_id,
                Connector.tenant_id == current_user.tenant_id,
            )
        )).scalar_one_or_none()
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {step_data.connector_id} not found",
            )

    pipeline = Pipeline(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description,
        merge_strategy=payload.merge_strategy,
        output_transform=payload.output_transform,
        created_by=current_user.id,
    )
    db.add(pipeline)
    await db.flush()

    for step_data in payload.steps:
        step = PipelineStep(
            pipeline_id=pipeline.id,
            connector_id=step_data.connector_id,
            step_order=step_data.step_order,
            name=step_data.name,
            execution_mode=step_data.execution_mode,
            params_template=step_data.params_template,
            condition=step_data.condition,
            on_error=step_data.on_error,
            timeout_seconds=step_data.timeout_seconds,
        )
        db.add(step)

    await db.commit()
    await db.refresh(pipeline)
    return await _build_pipeline_read(pipeline, db)


@router.get("/{pipeline_id}", response_model=PipelineRead, summary="Détail d'un pipeline")
async def get_pipeline(
    pipeline_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineRead:
    pipeline = await _get_pipeline(pipeline_id, current_user.tenant_id, db)
    return await _build_pipeline_read(pipeline, db)


@router.put("/{pipeline_id}", response_model=PipelineRead, summary="Modifier un pipeline")
async def update_pipeline(
    pipeline_id: uuid.UUID,
    payload: PipelineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineRead:
    pipeline = await _get_pipeline(pipeline_id, current_user.tenant_id, db)

    if payload.name is not None:
        pipeline.name = payload.name
    if payload.description is not None:
        pipeline.description = payload.description
    if payload.is_active is not None:
        pipeline.is_active = payload.is_active
    if payload.merge_strategy is not None:
        pipeline.merge_strategy = payload.merge_strategy
    if payload.output_transform is not None:
        pipeline.output_transform = payload.output_transform

    if payload.steps is not None:
        # Validate connectors
        for step_data in payload.steps:
            connector = (await db.execute(
                select(Connector).where(
                    Connector.id == step_data.connector_id,
                    Connector.tenant_id == current_user.tenant_id,
                )
            )).scalar_one_or_none()
            if connector is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Connector {step_data.connector_id} not found",
                )

        # Replace all steps
        existing_steps = (await db.execute(
            select(PipelineStep).where(PipelineStep.pipeline_id == pipeline.id)
        )).scalars().all()
        for s in existing_steps:
            await db.delete(s)
        await db.flush()

        for step_data in payload.steps:
            step = PipelineStep(
                pipeline_id=pipeline.id,
                connector_id=step_data.connector_id,
                step_order=step_data.step_order,
                name=step_data.name,
                execution_mode=step_data.execution_mode,
                params_template=step_data.params_template,
                condition=step_data.condition,
                on_error=step_data.on_error,
                timeout_seconds=step_data.timeout_seconds,
            )
            db.add(step)

    await db.commit()
    await db.refresh(pipeline)
    return await _build_pipeline_read(pipeline, db)


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Supprimer un pipeline")
async def delete_pipeline(
    pipeline_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    pipeline = await _get_pipeline(pipeline_id, current_user.tenant_id, db)
    await db.delete(pipeline)
    await db.commit()


@router.post("/{pipeline_id}/execute", summary="Exécuter un pipeline")
async def execute_pipeline(
    pipeline_id: uuid.UUID,
    payload: PipelineExecuteRequest,
    auth: Annotated[tuple[uuid.UUID, str], Depends(get_execute_auth)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant_id, triggered_by = auth

    pipeline = (await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    if not pipeline.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline is disabled")

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    engine = PipelineEngine()
    try:
        exec_result = await engine.execute(
            pipeline=pipeline,
            input_params=payload.params,
            tenant=tenant,
            db=db,
            triggered_by=triggered_by,
        )
    except (LicenseSuspendedError, LicenseExpiredError, QuotaExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))

    # Serialize steps for storage
    steps_detail = {
        str(order): {
            "status": sr.status,
            "result": sr.result,
            "error_message": sr.error_message,
            "duration_ms": sr.duration_ms,
            "connector_id": str(sr.connector_id),
        }
        for order, sr in exec_result.steps.items()
    }

    pe = PipelineExecution(
        pipeline_id=pipeline_id,
        tenant_id=tenant_id,
        triggered_by=triggered_by,
        status=exec_result.status,
        input_params=payload.params,
        result=exec_result.result,
        steps_detail=steps_detail,
        duration_ms=exec_result.duration_ms,
        error_step=exec_result.error_step,
        error_message=exec_result.error_message,
    )
    db.add(pe)
    await db.commit()
    await db.refresh(pe)

    return {
        "execution_id": str(pe.id),
        "status": exec_result.status,
        "result": exec_result.result,
        "steps": steps_detail,
        "duration_ms": exec_result.duration_ms,
        "error_step": exec_result.error_step,
        "error_message": exec_result.error_message,
    }


@router.get("/{pipeline_id}/executions", response_model=list[PipelineExecutionRead],
            summary="Historique d'exécutions du pipeline")
async def list_pipeline_executions(
    pipeline_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PipelineExecutionRead]:
    await _get_pipeline(pipeline_id, current_user.tenant_id, db)

    executions = (await db.execute(
        select(PipelineExecution)
        .where(PipelineExecution.pipeline_id == pipeline_id)
        .order_by(PipelineExecution.created_at.desc())
        .limit(100)
    )).scalars().all()

    return [PipelineExecutionRead.model_validate(e) for e in executions]


@router.post("/{pipeline_id}/test-step", summary="Tester un step isolément")
async def test_step(
    pipeline_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute a single step with resolved params (no quota increment, no logging)."""
    pipeline = await _get_pipeline(pipeline_id, current_user.tenant_id, db)

    step_order: int = body.get("step_order", 1)
    input_params: dict = body.get("input_params", {})
    completed_steps_raw: dict = body.get("completed_steps", {})

    step = (await db.execute(
        select(PipelineStep).where(
            PipelineStep.pipeline_id == pipeline.id,
            PipelineStep.step_order == step_order,
        )
    )).scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")

    from app.services.pipeline_resolver import PipelineResolver, StepResult
    resolver = PipelineResolver()
    resolved_params = resolver.resolve(step.params_template, input_params, {})

    return {
        "step_order": step_order,
        "connector_id": str(step.connector_id),
        "resolved_params": resolved_params,
        "condition": step.condition,
    }
