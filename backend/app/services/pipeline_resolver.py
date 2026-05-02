"""Pipeline variable resolver — resolves {{input.X}}, {{steps.N.result.X}}, {{steps.N.status}}."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Literal
import uuid


@dataclass
class StepResult:
    step_order: int
    connector_id: uuid.UUID
    status: Literal["success", "error", "skipped"]
    result: dict
    error_message: str | None
    duration_ms: int


_VAR_RE = re.compile(r"\{\{([^}]+)\}\}")


def _get_nested(data: Any, path: str) -> Any:
    """Navigate dot-notation path into nested dicts/lists. Returns '' on missing."""
    current = data
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return ""
        else:
            return ""
    return current


def _resolve_var(
    var: str,
    input_params: dict,
    completed_steps: dict[int, StepResult],
    tenant_id: str | None = None,
) -> Any:
    var = var.strip()

    if var.startswith("input."):
        return _get_nested(input_params, var[6:])

    if var.startswith("steps."):
        rest = var[6:]
        dot = rest.find(".")
        if dot == -1:
            return ""
        step_num_str = rest[:dot]
        remainder = rest[dot + 1:]
        try:
            step_num = int(step_num_str)
        except ValueError:
            return ""
        step = completed_steps.get(step_num)
        if step is None:
            return ""
        if remainder == "status":
            return step.status
        if remainder.startswith("result."):
            return _get_nested(step.result, remainder[7:])
        if remainder == "result":
            return step.result
        return ""

    if var == "tenant.id":
        return tenant_id or ""

    return ""


def _resolve_value(
    value: Any,
    input_params: dict,
    completed_steps: dict[int, StepResult],
    tenant_id: str | None = None,
) -> Any:
    if isinstance(value, str):
        matches = _VAR_RE.findall(value)
        if not matches:
            return value
        if len(matches) == 1 and value.strip() == "{{" + matches[0] + "}}":
            return _resolve_var(matches[0], input_params, completed_steps, tenant_id)
        result = value
        for m in matches:
            resolved = _resolve_var(m, input_params, completed_steps, tenant_id)
            result = result.replace("{{" + m + "}}", str(resolved))
        return result
    if isinstance(value, dict):
        return {k: _resolve_value(v, input_params, completed_steps, tenant_id) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(i, input_params, completed_steps, tenant_id) for i in value]
    return value


class PipelineResolver:
    def resolve(
        self,
        template: dict,
        input_params: dict,
        completed_steps: dict[int, StepResult],
        tenant_id: str | None = None,
    ) -> dict:
        return _resolve_value(template, input_params, completed_steps, tenant_id)  # type: ignore[return-value]

    def resolve_condition(
        self,
        condition: str,
        input_params: dict,
        completed_steps: dict[int, StepResult],
        tenant_id: str | None = None,
    ) -> bool:
        resolved = _resolve_value(condition, input_params, completed_steps, tenant_id)
        if isinstance(resolved, bool):
            return resolved
        resolved_str = str(resolved).strip()

        # Supported: LHS OP RHS where OP in ==, !=, >=, <=, >, <
        for op in ("==", "!=", ">=", "<=", ">", "<"):
            if op in resolved_str:
                parts = resolved_str.split(op, 1)
                if len(parts) == 2:
                    lhs, rhs = parts[0].strip(), parts[1].strip()
                    try:
                        lhs_val = ast.literal_eval(lhs)
                    except (ValueError, SyntaxError):
                        lhs_val = lhs.strip("'\"")
                    try:
                        rhs_val = ast.literal_eval(rhs)
                    except (ValueError, SyntaxError):
                        rhs_val = rhs.strip("'\"")
                    try:
                        if op == "==":
                            return lhs_val == rhs_val
                        if op == "!=":
                            return lhs_val != rhs_val
                        if op == ">=":
                            return float(lhs_val) >= float(rhs_val)
                        if op == "<=":
                            return float(lhs_val) <= float(rhs_val)
                        if op == ">":
                            return float(lhs_val) > float(rhs_val)
                        if op == "<":
                            return float(lhs_val) < float(rhs_val)
                    except (TypeError, ValueError):
                        return False

        # Bare truthy check
        lower = resolved_str.lower()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no", ""):
            return False
        return bool(resolved_str)
