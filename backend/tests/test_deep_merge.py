from app.services.pipeline_engine import deep_merge


def test_merge_simple():
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_merge_override():
    assert deep_merge({"a": 1, "b": 2}, {"b": 99}) == {"a": 1, "b": 99}


def test_merge_nested():
    base = {"a": {"x": 1, "y": 2}}
    override = {"a": {"y": 99, "z": 3}}
    result = deep_merge(base, override)
    assert result == {"a": {"x": 1, "y": 99, "z": 3}}


def test_merge_deep_nested():
    base = {"a": {"b": {"c": 1}}}
    override = {"a": {"b": {"d": 2}}}
    result = deep_merge(base, override)
    assert result == {"a": {"b": {"c": 1, "d": 2}}}


def test_merge_list_override():
    # Lists are overridden, not merged
    base = {"items": [1, 2]}
    override = {"items": [3, 4, 5]}
    result = deep_merge(base, override)
    assert result["items"] == [3, 4, 5]


def test_merge_empty_base():
    assert deep_merge({}, {"a": 1}) == {"a": 1}


def test_merge_empty_override():
    assert deep_merge({"a": 1}, {}) == {"a": 1}
