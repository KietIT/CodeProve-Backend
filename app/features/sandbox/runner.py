"""Subprocess sandbox: runs user code + test expressions in an isolated Python
process with a timeout. MVP-grade isolation (not container-level). Interface is
stable so a Docker backend can replace it later."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

_HARNESS = '''
import json, sys, io, contextlib
USER_SOURCE = {source!r}
CASES = json.loads({cases!r})
ns = {{}}
results = []
runtime_error = None
try:
    exec(USER_SOURCE, ns)
except Exception as e:  # noqa: BLE001
    runtime_error = f"{{type(e).__name__}}: {{e}}"
if runtime_error is None:
    for c in CASES:
        out = {{"name": c["description"], "passed": False, "stdout": "", "error": None}}
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                value = eval(c["input_data"], ns)
            got = repr(value)
            out["stdout"] = buf.getvalue()[:2000]
            out["passed"] = (got == c["expected_output"]) or (buf.getvalue().strip() == c["expected_output"].strip())
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{{type(e).__name__}}: {{e}}"
        results.append(out)
print(json.dumps({{"results": results, "runtime_error": runtime_error}}))
'''


async def run_tests(source_code: str, test_cases: list[dict], timeout: int) -> dict:
    harness = _HARNESS.format(source=source_code, cases=json.dumps(test_cases))
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "runner.py"
        script.write_text(harness, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", str(script),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=2)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
            return _result([], f"Timeout after {timeout}s", test_cases)
        finally:
            # Release the subprocess pipe transports so a killed process does not
            # leak file descriptors (avoids the ProactorEventLoop ResourceWarning).
            transport = getattr(proc, "_transport", None)
            if transport is not None:
                transport.close()
        if proc.returncode != 0 and not stdout:
            return _result([], (stderr.decode()[:500] or "Process error"), test_cases)
        try:
            data = json.loads(stdout.decode().strip().splitlines()[-1])
        except (ValueError, IndexError):
            return _result([], "Invalid runner output", test_cases)
        return _result(data["results"], data["runtime_error"], test_cases)


def _result(cases: list[dict], runtime_error: str | None, test_cases: list[dict]) -> dict:
    total = len(test_cases)
    if not cases:
        cases = [{"name": c["description"], "passed": False, "stdout": "", "error": runtime_error} for c in test_cases]
    passed = sum(1 for c in cases if c["passed"])
    coverage = round(passed / total, 3) if total else 0.0
    return {"passed": passed, "total": total, "coverage": coverage, "cases": cases, "runtime_error": runtime_error}
