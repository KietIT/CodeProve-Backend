import os
import sys

import pytest

from app.features.sandbox.runner import run_tests, trace_code

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


# ── Isolation: user code must not see the backend's secrets ─────────────────
SECRET_NAME = "CODEPROVE_TEST_SECRET"
SECRET_VALUE = "s3cr3t-must-not-leak"
LEAK_SOURCE = "import os\nLEAK = os.environ.get('CODEPROVE_TEST_SECRET', 'absent')\nprint(dict(os.environ))\n"


async def test_run_tests_does_not_expose_parent_env(monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET_VALUE)
    cases = [{"input_data": "LEAK", "expected_output": "'absent'", "description": "env", "weight": 1.0}]
    res = await run_tests(LEAK_SOURCE, cases, timeout=5)
    assert res["runtime_error"] is None
    assert res["cases"][0]["passed"] is True, res
    assert SECRET_VALUE not in repr(res)


async def test_trace_code_does_not_expose_parent_env(monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET_VALUE)
    res = await trace_code(LEAK_SOURCE, "", timeout=5)
    assert res["error"] is None, res
    assert "absent" in repr(res["frames"])
    assert SECRET_VALUE not in repr(res)
    assert SECRET_NAME not in res["stdout"]


async def test_user_code_runs_in_scratch_cwd():
    # The child starts in its own temp dir, not the backend's working directory
    # (which holds .env and the app source).
    src = "import os\nIN_REPO = os.path.exists('pytest.ini') or os.path.exists('.env')\ndone = True\n"
    res = await trace_code(src, "", timeout=5)
    assert res["error"] is None, res
    assert res["frames"][-1]["locals"]["IN_REPO"] == {"kind": "scalar", "value": "False"}


@pytest.mark.skipif(sys.platform == "win32", reason="rlimits are POSIX-only")
async def test_memory_limit_stops_huge_allocation():
    cases = [{"input_data": "len(bytearray(2 * 1024 ** 3))", "expected_output": "0", "description": "mem", "weight": 1.0}]
    res = await run_tests("", cases, timeout=5)
    assert res["cases"][0]["passed"] is False
    assert "MemoryError" in (res["cases"][0]["error"] or "")


def _can_drop_to_sandbox_user() -> bool:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return False
    import pwd

    try:
        pwd.getpwnam("sandbox")
    except KeyError:
        return False
    return True


@pytest.mark.skipif(not _can_drop_to_sandbox_user(), reason="needs root + `sandbox` user (Docker image)")
async def test_child_cannot_read_backend_process_environ():
    src = (
        "import os\n"
        "try:\n"
        "    open('/proc/%d/environ' % os.getppid()).read()\n"
        "    READ = 'leaked'\n"
        "except PermissionError:\n"
        "    READ = 'denied'\n"
        "UID = os.getuid()\n"
    )
    cases = [{"input_data": "(READ, UID != 0)", "expected_output": "('denied', True)", "description": "proc", "weight": 1.0}]
    res = await run_tests(src, cases, timeout=5)
    assert res["cases"][0]["passed"] is True, res


async def test_run_tests_reports_the_actual_value():
    cases = [{"input_data": "f()", "expected_output": "42", "description": "answer", "weight": 1.0}]
    res = await run_tests("def f():\n    return 41", cases, timeout=5)
    assert res["cases"][0]["passed"] is False
    assert res["cases"][0]["actual"] == "41"
