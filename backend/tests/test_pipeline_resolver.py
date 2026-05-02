import uuid
import pytest

from app.services.pipeline_resolver import PipelineResolver, StepResult


def _make_step(order: int, status: str = "success", result: dict = None) -> StepResult:
    return StepResult(
        step_order=order,
        connector_id=uuid.uuid4(),
        status=status,
        result=result or {},
        error_message=None,
        duration_ms=10,
    )


resolver = PipelineResolver()


def test_resolve_input_simple():
    result = resolver.resolve({"name": "{{input.user}}"}, {"user": "Alice"}, {})
    assert result == {"name": "Alice"}


def test_resolve_input_nested_path():
    result = resolver.resolve(
        {"city": "{{input.address.city}}"},
        {"address": {"city": "Paris"}},
        {},
    )
    assert result == {"city": "Paris"}


def test_resolve_steps_result_dot_notation():
    step1 = _make_step(1, result={"contract": {"id": "C-42", "amount": 1000}})
    result = resolver.resolve(
        {"contract_id": "{{steps.1.result.contract.id}}"},
        {},
        {1: step1},
    )
    assert result == {"contract_id": "C-42"}


def test_resolve_steps_status():
    step1 = _make_step(1, status="success")
    result = resolver.resolve({"s": "{{steps.1.status}}"}, {}, {1: step1})
    assert result == {"s": "success"}


def test_resolve_missing_variable_returns_empty():
    result = resolver.resolve({"x": "{{input.nonexistent}}"}, {}, {})
    assert result == {"x": ""}


def test_resolve_missing_step_returns_empty():
    result = resolver.resolve({"x": "{{steps.99.result.foo}}"}, {}, {})
    assert result == {"x": ""}


def test_resolve_mixed_string():
    step1 = _make_step(1, result={"score": 85})
    result = resolver.resolve(
        {"msg": "Score: {{steps.1.result.score}} / 100"},
        {},
        {1: step1},
    )
    assert result == {"msg": "Score: 85 / 100"}


def test_resolve_nested_template():
    result = resolver.resolve(
        {"outer": {"inner": "{{input.val}}"}},
        {"val": "hello"},
        {},
    )
    assert result == {"outer": {"inner": "hello"}}


def test_condition_equality():
    step1 = _make_step(1, status="success")
    assert resolver.resolve_condition("{{steps.1.status}} == 'success'", {}, {1: step1}) is True
    assert resolver.resolve_condition("{{steps.1.status}} == 'error'", {}, {1: step1}) is False


def test_condition_numeric_comparison():
    step1 = _make_step(1, result={"score": 75})
    assert resolver.resolve_condition("{{steps.1.result.score}} > 50", {}, {1: step1}) is True
    assert resolver.resolve_condition("{{steps.1.result.score}} > 80", {}, {1: step1}) is False


def test_condition_not_equal():
    step1 = _make_step(1, status="error")
    assert resolver.resolve_condition("{{steps.1.status}} != 'success'", {}, {1: step1}) is True


def test_tenant_id_variable():
    tid = str(uuid.uuid4())
    result = resolver.resolve({"tid": "{{tenant.id}}"}, {}, {}, tenant_id=tid)
    assert result == {"tid": tid}
