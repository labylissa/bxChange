"""Pipeline orchestration engine."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import Connector
from app.models.pipeline import Pipeline, PipelineStep
from app.models.tenant import Tenant
from app.services import transformer
from app.services.execution_service import (
    LicenseExpiredError,
    LicenseSuspendedError,
    QuotaExceededError,
    check_license_and_quota,
    execute_connector,
)
from app.services.pipeline_resolver import PipelineResolver, StepResult


@dataclass
class PipelineExecutionResult:
    status: Literal["success", "error"]
    result: dict = field(default_factory=dict)
    steps: dict[int, StepResult] = field(default_factory=dict)
    error_step: int | None = None
    error_message: str | None = None
    duration_ms: int = 0


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _group_steps(steps: list[PipelineStep]) -> list[list[PipelineStep]]:
    """Group steps by step_order; same order = parallel group."""
    order_map: dict[int, list[PipelineStep]] = {}
    for step in sorted(steps, key=lambda s: s.step_order):
        order_map.setdefault(step.step_order, []).append(step)
    return [group for _, group in sorted(order_map.items())]


def _merge_results(strategy: str, completed_steps: dict[int, StepResult]) -> dict:
    successful = {k: v for k, v in completed_steps.items() if v.status == "success"}
    if not successful:
        return {}

    if strategy == "merge":
        merged: dict = {}
        for sr in sorted(successful.values(), key=lambda x: x.step_order):
            merged = deep_merge(merged, sr.result)
        return merged

    if strategy == "first":
        return min(successful.values(), key=lambda x: x.step_order).result

    if strategy == "last":
        return max(successful.values(), key=lambda x: x.step_order).result

    if strategy == "custom":
        return {f"step_{k}": v.result for k, v in successful.items()}

    return {}


class PipelineEngine:

    async def execute(
        self,
        pipeline: Pipeline,
        input_params: dict,
        tenant: Tenant,
        db: AsyncSession,
        triggered_by: str = "manual",
    ) -> PipelineExecutionResult:
        resolver = PipelineResolver()
        completed_steps: dict[int, StepResult] = {}

        steps_result = await db.execute(
            select(PipelineStep).where(PipelineStep.pipeline_id == pipeline.id)
        )
        steps = list(steps_result.scalars().all())
        step_groups = _group_steps(steps)

        total_start = time.monotonic()

        for group in step_groups:
            if len(group) == 1:
                result = await self._execute_step(
                    group[0], input_params, completed_steps, resolver, tenant, db, triggered_by
                )
                completed_steps[group[0].step_order] = result

                if result.status == "error" and group[0].on_error == "stop":
                    return PipelineExecutionResult(
                        status="error",
                        error_step=group[0].step_order,
                        error_message=result.error_message,
                        steps=completed_steps,
                        duration_ms=int((time.monotonic() - total_start) * 1000),
                    )
            else:
                results = await asyncio.gather(
                    *[
                        self._execute_step(
                            step, input_params, completed_steps, resolver, tenant, db, triggered_by
                        )
                        for step in group
                    ],
                    return_exceptions=True,
                )
                stop_pipeline = False
                for step, res in zip(group, results):
                    if isinstance(res, Exception):
                        sr = StepResult(
                            step_order=step.step_order,
                            connector_id=step.connector_id,
                            status="error",
                            result={},
                            error_message=str(res),
                            duration_ms=0,
                        )
                    else:
                        sr = res
                    completed_steps[step.step_order] = sr
                    if sr.status == "error" and step.on_error == "stop":
                        stop_pipeline = True

                if stop_pipeline:
                    errored = [
                        (k, v) for k, v in completed_steps.items() if v.status == "error"
                    ]
                    first_err_order, first_err = min(errored, key=lambda x: x[0])
                    return PipelineExecutionResult(
                        status="error",
                        error_step=first_err_order,
                        error_message=first_err.error_message,
                        steps=completed_steps,
                        duration_ms=int((time.monotonic() - total_start) * 1000),
                    )

        merged = _merge_results(pipeline.merge_strategy, completed_steps)

        if pipeline.output_transform:
            try:
                merged = transformer.transform(merged, pipeline.output_transform)
            except Exception:
                pass

        return PipelineExecutionResult(
            status="success",
            result=merged,
            steps=completed_steps,
            duration_ms=int((time.monotonic() - total_start) * 1000),
        )

    async def _execute_step(
        self,
        step: PipelineStep,
        input_params: dict,
        completed_steps: dict[int, StepResult],
        resolver: PipelineResolver,
        tenant: Tenant,
        db: AsyncSession,
        triggered_by: str,
    ) -> StepResult:
        start = time.monotonic()

        # Evaluate condition
        if step.condition:
            try:
                should_run = resolver.resolve_condition(
                    step.condition, input_params, completed_steps, str(tenant.id)
                )
            except Exception:
                should_run = False
            if not should_run:
                return StepResult(
                    step_order=step.step_order,
                    connector_id=step.connector_id,
                    status="skipped",
                    result={},
                    error_message=None,
                    duration_ms=0,
                )

        # Resolve params template
        resolved_params = resolver.resolve(
            step.params_template, input_params, completed_steps, str(tenant.id)
        )

        # If the template left connector-critical keys unset, fall back to input_params.
        # This lets callers pass {"operation": "..."} without templating every step.
        for _key in ("operation", "method", "path"):
            if _key not in resolved_params and _key in input_params:
                resolved_params = {**resolved_params, _key: input_params[_key]}

        try:
            # Quota check — each step = 1 execution
            await check_license_and_quota(tenant)

            exec_read = await asyncio.wait_for(
                execute_connector(
                    connector_id=step.connector_id,
                    tenant_id=tenant.id,
                    params=resolved_params,
                    body=None,
                    transform_override=None,
                    triggered_by=triggered_by,
                    db=db,
                    _skip_quota=True,  # already checked above
                ),
                timeout=step.timeout_seconds,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            if exec_read.status == "error":
                if step.on_error == "skip":
                    return StepResult(
                        step_order=step.step_order,
                        connector_id=step.connector_id,
                        status="skipped",
                        result={},
                        error_message=exec_read.error_message,
                        duration_ms=duration_ms,
                    )
                return StepResult(
                    step_order=step.step_order,
                    connector_id=step.connector_id,
                    status="error",
                    result={},
                    error_message=exec_read.error_message,
                    duration_ms=duration_ms,
                )

            return StepResult(
                step_order=step.step_order,
                connector_id=step.connector_id,
                status="success",
                result=exec_read.response_payload or {},
                error_message=None,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            return StepResult(
                step_order=step.step_order,
                connector_id=step.connector_id,
                status="error",
                result={},
                error_message=f"Timeout après {step.timeout_seconds}s",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except (LicenseSuspendedError, LicenseExpiredError, QuotaExceededError) as exc:
            return StepResult(
                step_order=step.step_order,
                connector_id=step.connector_id,
                status="error",
                result={},
                error_message=str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as exc:
            if step.on_error == "skip":
                return StepResult(
                    step_order=step.step_order,
                    connector_id=step.connector_id,
                    status="skipped",
                    result={},
                    error_message=str(exc),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            return StepResult(
                step_order=step.step_order,
                connector_id=step.connector_id,
                status="error",
                result={},
                error_message=str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
