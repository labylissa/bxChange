from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class PipelineStepCreate(BaseModel):
    connector_id: uuid.UUID
    step_order: int
    name: str
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    params_template: dict = {}
    condition: str | None = None
    on_error: Literal["stop", "skip", "continue"] = "stop"
    timeout_seconds: int = 30


class PipelineStepRead(PipelineStepCreate):
    id: uuid.UUID
    connector_name: str
    connector_type: str

    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    merge_strategy: Literal["merge", "first", "last", "custom"] = "merge"
    output_transform: dict | None = None
    steps: list[PipelineStepCreate]

    @field_validator("steps")
    @classmethod
    def at_least_two_steps(cls, v: list[PipelineStepCreate]) -> list[PipelineStepCreate]:
        if len(v) < 2:
            raise ValueError("Un pipeline doit avoir au moins 2 étapes")
        return v

    @model_validator(mode="after")
    def unique_step_orders(self) -> PipelineCreate:
        orders = [s.step_order for s in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("step_order doit être unique dans un pipeline")
        return self


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    merge_strategy: Literal["merge", "first", "last", "custom"] | None = None
    output_transform: dict | None = None
    steps: list[PipelineStepCreate] | None = None

    @field_validator("steps")
    @classmethod
    def at_least_two_steps(cls, v: list[PipelineStepCreate] | None) -> list[PipelineStepCreate] | None:
        if v is not None and len(v) < 2:
            raise ValueError("Un pipeline doit avoir au moins 2 étapes")
        return v


class PipelineRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    merge_strategy: str
    output_transform: dict | None
    steps: list[PipelineStepRead]
    created_at: datetime
    executions_count: int = 0

    model_config = {"from_attributes": True}


class PipelineExecutionRead(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    tenant_id: uuid.UUID
    triggered_by: str
    status: str
    input_params: dict
    result: dict
    steps_detail: dict
    duration_ms: int
    error_step: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineExecuteRequest(BaseModel):
    params: dict = {}
