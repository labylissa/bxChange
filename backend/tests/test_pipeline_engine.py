import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.pipeline_engine import PipelineEngine, _merge_results, _group_steps, deep_merge
from app.services.pipeline_resolver import StepResult


def _sr(order: int, status: str = "success", result: dict = None):
    return StepResult(
        step_order=order,
        connector_id=uuid.uuid4(),
        status=status,
        result=result or {"step": order},
        error_message=None if status != "error" else "fail",
        duration_ms=10,
    )


# ── merge strategies ───────────────────────────────────────────────────────────

def test_merge_strategy_merge():
    steps = {1: _sr(1, result={"a": 1}), 2: _sr(2, result={"b": 2})}
    result = _merge_results("merge", steps)
    assert result == {"a": 1, "b": 2}


def test_merge_strategy_first():
    steps = {1: _sr(1, result={"a": 1}), 2: _sr(2, result={"b": 2})}
    assert _merge_results("first", steps) == {"a": 1}


def test_merge_strategy_last():
    steps = {1: _sr(1, result={"a": 1}), 2: _sr(2, result={"b": 2})}
    assert _merge_results("last", steps) == {"b": 2}


def test_merge_strategy_custom():
    steps = {1: _sr(1, result={"a": 1}), 2: _sr(2, result={"b": 2})}
    result = _merge_results("custom", steps)
    assert "step_1" in result
    assert "step_2" in result


def test_merge_skips_errored_steps():
    steps = {1: _sr(1, result={"a": 1}), 2: _sr(2, status="error", result={})}
    result = _merge_results("merge", steps)
    assert result == {"a": 1}


def test_merge_empty_returns_empty():
    assert _merge_results("merge", {}) == {}


# ── step grouping ──────────────────────────────────────────────────────────────

class _FakeStep:
    def __init__(self, order: int):
        self.step_order = order
        self.id = uuid.uuid4()


def test_group_steps_sequential():
    steps = [_FakeStep(1), _FakeStep(2), _FakeStep(3)]
    groups = _group_steps(steps)
    assert len(groups) == 3
    assert all(len(g) == 1 for g in groups)


def test_group_steps_parallel():
    steps = [_FakeStep(1), _FakeStep(2), _FakeStep(2)]
    groups = _group_steps(steps)
    assert len(groups) == 2
    assert len(groups[0]) == 1
    assert len(groups[1]) == 2


# ── engine integration (mocked execute_connector) ─────────────────────────────

class _FakePipelineStep:
    def __init__(self, order, connector_id, on_error="stop", condition=None, timeout=30):
        self.id = uuid.uuid4()
        self.step_order = order
        self.connector_id = connector_id
        self.execution_mode = "sequential"
        self.params_template = {}
        self.condition = condition
        self.on_error = on_error
        self.timeout_seconds = timeout
        self.name = f"step_{order}"


class _FakePipeline:
    def __init__(self, merge_strategy="merge", output_transform=None):
        self.id = uuid.uuid4()
        self.merge_strategy = merge_strategy
        self.output_transform = output_transform


class _FakeTenant:
    def __init__(self):
        self.id = uuid.uuid4()
        self.license_status = "active"
        self.executions_used = 0
        self.executions_limit = 1000
        self.trial_ends_at = None


class _FakeExecRead:
    def __init__(self, result, status="success", error=None):
        self.response_payload = result
        self.status = status
        self.error_message = error
        self.id = uuid.uuid4()


class _FakeDB:
    """Minimal async DB mock for engine tests."""
    def __init__(self, steps):
        self._steps = steps

    async def execute(self, *args, **kwargs):
        class _R:
            def __init__(self, items):
                self._items = items
            def scalars(self):
                return self
            def all(self):
                return self._items
        return _R(self._steps)

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.mark.asyncio
async def test_sequential_two_steps_success():
    cid1, cid2 = uuid.uuid4(), uuid.uuid4()
    steps = [_FakePipelineStep(1, cid1), _FakePipelineStep(2, cid2)]
    pipeline = _FakePipeline(merge_strategy="merge")
    tenant = _FakeTenant()
    db = _FakeDB(steps)

    exec_results = [
        _FakeExecRead({"a": 1}),
        _FakeExecRead({"b": 2}),
    ]
    call_idx = [0]

    async def fake_execute(**kwargs):
        r = exec_results[call_idx[0]]
        call_idx[0] += 1
        return r

    with patch("app.services.pipeline_engine.execute_connector", side_effect=fake_execute), \
         patch("app.services.pipeline_engine.check_license_and_quota", new=AsyncMock()):
        engine = PipelineEngine()
        result = await engine.execute(pipeline, {}, tenant, db)

    assert result.status == "success"
    assert result.result == {"a": 1, "b": 2}
    assert len(result.steps) == 2


@pytest.mark.asyncio
async def test_on_error_stop():
    cid1, cid2 = uuid.uuid4(), uuid.uuid4()
    steps = [_FakePipelineStep(1, cid1, on_error="stop"), _FakePipelineStep(2, cid2)]
    pipeline = _FakePipeline()
    tenant = _FakeTenant()
    db = _FakeDB(steps)

    exec_results = [_FakeExecRead({}, status="error", error="boom")]
    call_idx = [0]

    async def fake_execute(**kwargs):
        r = exec_results[call_idx[0]]
        call_idx[0] += 1
        return r

    with patch("app.services.pipeline_engine.execute_connector", side_effect=fake_execute), \
         patch("app.services.pipeline_engine.check_license_and_quota", new=AsyncMock()):
        engine = PipelineEngine()
        result = await engine.execute(pipeline, {}, tenant, db)

    assert result.status == "error"
    assert result.error_step == 1
    assert len(result.steps) == 1  # step 2 never ran


@pytest.mark.asyncio
async def test_on_error_skip_continues():
    cid1, cid2 = uuid.uuid4(), uuid.uuid4()
    steps = [_FakePipelineStep(1, cid1, on_error="skip"), _FakePipelineStep(2, cid2)]
    pipeline = _FakePipeline(merge_strategy="last")
    tenant = _FakeTenant()
    db = _FakeDB(steps)

    exec_results = [
        _FakeExecRead({}, status="error", error="fail"),
        _FakeExecRead({"ok": True}),
    ]
    call_idx = [0]

    async def fake_execute(**kwargs):
        r = exec_results[call_idx[0]]
        call_idx[0] += 1
        return r

    with patch("app.services.pipeline_engine.execute_connector", side_effect=fake_execute), \
         patch("app.services.pipeline_engine.check_license_and_quota", new=AsyncMock()):
        engine = PipelineEngine()
        result = await engine.execute(pipeline, {}, tenant, db)

    assert result.status == "success"
    assert result.result == {"ok": True}
