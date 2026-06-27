import pytest

from app.features.sandbox.runner import run_tests

pytestmark = pytest.mark.asyncio


async def test_runs_passing_cases():
    src = "def add(a, b):\n    return a + b"
    cases = [
        {"input_data": "add(2, 3)", "expected_output": "5", "description": "t1", "weight": 1.0},
        {"input_data": "add(-1, 1)", "expected_output": "0", "description": "t2", "weight": 1.0},
    ]
    res = await run_tests(src, cases, timeout=5)
    assert res["passed"] == 2
    assert res["total"] == 2
    assert res["coverage"] == 1.0


async def test_reports_failure_and_does_not_crash_on_bad_code():
    src = "def add(a, b):\n    return a - b"  # wrong
    cases = [{"input_data": "add(2, 3)", "expected_output": "5", "description": "t1", "weight": 1.0}]
    res = await run_tests(src, cases, timeout=5)
    assert res["passed"] == 0
    assert res["cases"][0]["passed"] is False


async def test_timeout_is_handled():
    src = "def loop():\n    while True:\n        pass"
    cases = [{"input_data": "loop()", "expected_output": "None", "description": "t1", "weight": 1.0}]
    res = await run_tests(src, cases, timeout=1)
    assert res["passed"] == 0
    assert res["total"] == 1
    assert res["coverage"] == 0.0
    assert len(res["cases"]) == 1
    assert res["runtime_error"] is not None
