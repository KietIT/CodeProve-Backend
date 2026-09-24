"""Subprocess sandbox: runs user code + test expressions in a separate Python
process with a timeout. MVP-grade isolation (not container-level). Interface is
stable so a Docker backend can replace it later.

What this layer does:
  - the child gets a minimal env (no API keys, JWT secret, DATABASE_URL, ...);
  - it starts in a private scratch dir, not the backend's working directory;
  - on POSIX it runs under rlimits (memory, CPU, file size, no core dumps);
  - when the backend runs as root and a `sandbox` user exists (see Dockerfile),
    it runs as that unprivileged user, so it cannot read the backend's
    /proc/<pid>/environ or root-only files.

What it does NOT do: block network access (the child can still reach the `db`
service and the internet) or stop reads of world-readable files. Real isolation
needs a dedicated sandbox container with no network and no secrets (e.g. a
separate runner service using nsjail / gVisor / Firecracker) - tracked as
follow-up.
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SANDBOX_USER = "sandbox"
_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
_FILE_SIZE_LIMIT_BYTES = 1024 * 1024
# The sandbox user must be able to read the harness but never write next to it:
# owner-only write on both. Loosening these lets user code tamper with its cwd.
_SCRATCH_DIR_MODE = 0o755
_SCRATCH_FILE_MODE = 0o644

# Prepended to both harnesses: applies rlimits inside the child before any user
# code runs (done here rather than via preexec_fn, which is not safe to use from
# the worker threads that launch the subprocess).
_LIMITS_PRELUDE = """
import sys as _sys
if _sys.platform != "win32":
    import resource as _r
    for _res, _soft in ((_r.RLIMIT_AS, {memory}), (_r.RLIMIT_CPU, {cpu}),
                        (_r.RLIMIT_FSIZE, {fsize}), (_r.RLIMIT_CORE, 0)):
        _hard = _r.getrlimit(_res)[1]
        _v = _soft if _hard == _r.RLIM_INFINITY else min(_soft, _hard)
        _r.setrlimit(_res, (_v, _v))
    del _r, _res, _soft, _hard, _v
del _sys
"""


def _limits_prelude(timeout: int) -> str:
    return _LIMITS_PRELUDE.format(memory=_MEMORY_LIMIT_BYTES, cpu=timeout + 1, fsize=_FILE_SIZE_LIMIT_BYTES)


def _sandbox_env() -> dict[str, str]:
    """Explicit allow-list: nothing from the backend's environment leaks into
    user code. SYSTEMROOT is required for Python to start on Windows."""
    env = {"PATH": os.environ.get("PATH", os.defpath)}
    if sys.platform == "win32":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    else:
        env["LANG"] = "C.UTF-8"
    return env


def _sandbox_identity() -> dict[str, object]:
    """subprocess kwargs that drop root to the unprivileged sandbox user."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return {}
    import pwd

    try:
        pw = pwd.getpwnam(SANDBOX_USER)
    except KeyError:
        logger.warning("Sandbox user %r not found; running user code as root", SANDBOX_USER)
        return {}
    return {"user": pw.pw_uid, "group": pw.pw_gid, "extra_groups": []}


def _spawn(argv: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-I", *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # No interactive stdin: feed EOF so input() fails fast with EOFError
        # instead of blocking until the timeout.
        stdin=subprocess.DEVNULL,
        env=_sandbox_env(),
        cwd=cwd,
        timeout=timeout,
        check=False,
        **_sandbox_identity(),
    )


def _make_scratch_readable(tmp: Path) -> None:
    """TemporaryDirectory is 0700; the sandbox user needs to read the harness.
    Files stay read-only for it, so user code cannot write into its cwd."""
    tmp.chmod(_SCRATCH_DIR_MODE)
    for f in tmp.iterdir():
        f.chmod(_SCRATCH_FILE_MODE)

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
        out = {{"name": c["description"], "passed": False, "stdout": "", "error": None, "actual": None}}
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                value = eval(c["input_data"], ns)
            got = repr(value)
            out["actual"] = got[:500]
            out["stdout"] = buf.getvalue()[:2000]
            out["passed"] = (got == c["expected_output"]) or (buf.getvalue().strip() == c["expected_output"].strip())
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{{type(e).__name__}}: {{e}}"
        results.append(out)
print(json.dumps({{"results": results, "runtime_error": runtime_error}}))
'''


async def run_tests(source_code: str, test_cases: list[dict], timeout: int) -> dict:
    harness = _limits_prelude(timeout) + _HARNESS.format(source=source_code, cases=json.dumps(test_cases))
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "runner.py"
        script.write_text(harness, encoding="utf-8")
        _make_scratch_readable(Path(tmp))
        try:
            proc = await asyncio.to_thread(_run_script, script, timeout)
        except subprocess.TimeoutExpired:
            return _result([], f"Timeout after {timeout}s", test_cases)
        if proc.returncode != 0 and not proc.stdout:
            return _result([], (proc.stderr.decode()[:500] or "Process error"), test_cases)
        try:
            data = json.loads(proc.stdout.decode().strip().splitlines()[-1])
        except (ValueError, IndexError):
            return _result([], "Invalid runner output", test_cases)
        return _result(data["results"], data["runtime_error"], test_cases)


def _run_script(script: Path, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return _spawn([str(script)], script.parent, timeout)


# ── Execution trace (algorithm visualizer) ───────────────────────────────────
# Runs the user's code with sys.settrace and records one frame per executed line
# (line number + locals serialised to VizValue). The user code is compiled with
# the filename "user_code" so the tracer records only the student's lines, and
# line numbers map back to their source. Reuses the subprocess isolation above.
_TRACE_HARNESS = r'''
import json, sys, io, types, contextlib
with open(sys.argv[1], encoding="utf-8") as _f:
    _p = json.load(_f)
USER_SOURCE = _p["source"]; CALL = _p["call"]; MAX_FRAMES = 500
frames = []; error = None

# In practice mode the code runs at module scope, so frame.f_locals is the
# module globals - which Python auto-populates with __builtins__ and the
# user's own function/class/import bindings. None of that is a "variable" the
# student is tracking, so drop dunders and module/function/type values.
def _skip(n, v):
    if n.startswith("__") and n.endswith("__"):
        return True
    return isinstance(v, (types.ModuleType, types.FunctionType,
                          types.BuiltinFunctionType, type))

def _short(x):
    s = x if isinstance(x, str) else repr(x)
    return s if len(s) <= 60 else s[:57] + "..."

def _to_viz(v):
    if isinstance(v, bool):
        return {"kind": "scalar", "value": str(v)}
    if isinstance(v, (int, float, str)):
        return {"kind": "scalar", "value": _short(v)}
    if isinstance(v, (list, tuple)):
        return {"kind": "array", "items": [_short(x) for x in list(v)[:50]]}
    if isinstance(v, dict):
        return {"kind": "map", "entries": [[_short(k), _short(val)] for k, val in list(v.items())[:50]]}
    return {"kind": "scalar", "value": _short(v)}

def _tracer(frame, event, arg):
    if frame.f_code.co_filename != "user_code":
        return None
    if event == "line":
        if len(frames) >= MAX_FRAMES:
            raise RuntimeError("__cap__")
        raw = {n: v for n, v in frame.f_locals.items() if not _skip(n, v)}
        viz = {}
        for n, val in raw.items():
            try:
                viz[n] = _to_viz(val)
            except Exception:
                viz[n] = {"kind": "scalar", "value": "<unrepr>"}
        # Pointer inference: int vars whose value indexes into an array in scope.
        ints = {n: v for n, v in raw.items() if type(v) is int}
        for n, val in raw.items():
            if isinstance(val, (list, tuple)) and viz.get(n, {}).get("kind") == "array":
                length = len(val)
                ptrs = {a: b for a, b in ints.items() if 0 <= b < length}
                if ptrs:
                    viz[n]["ptrs"] = ptrs
        frames.append({"line": frame.f_lineno, "event": "line", "locals": viz})
    return _tracer

_buf = io.StringIO(); ns = {}
try:
    with contextlib.redirect_stdout(_buf):
        exec(compile(USER_SOURCE, "user_code", "exec"), ns)
        if CALL.strip():
            # Workspace: trace the student's function running on a sample input.
            sys.settrace(_tracer)
            try:
                eval(compile(CALL, "<call>", "eval"), ns)
            finally:
                sys.settrace(None)
        else:
            # Practice: no sample call - trace the script's own top-level run.
            sys.settrace(_tracer)
            try:
                exec(compile(USER_SOURCE, "user_code", "exec"), {})
            finally:
                sys.settrace(None)
except RuntimeError as e:
    sys.settrace(None)
    error = None if "__cap__" in str(e) else "%s: %s" % (type(e).__name__, e)
except EOFError:
    sys.settrace(None)
    error = "input() không hỗ trợ ở chế độ luyện tập — hãy gán giá trị cố định (ví dụ n = 7)."
except Exception as e:
    sys.settrace(None)
    error = "%s: %s" % (type(e).__name__, e)

print(json.dumps({"frames": frames, "stdout": _buf.getvalue()[:2000], "error": error}))
'''


async def trace_code(source_code: str, call: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "trace.py"
        script.write_text(_limits_prelude(timeout) + _TRACE_HARNESS, encoding="utf-8")
        payload = Path(tmp) / "payload.json"
        payload.write_text(json.dumps({"source": source_code, "call": call or ""}), encoding="utf-8")
        _make_scratch_readable(Path(tmp))
        try:
            proc = await asyncio.to_thread(_run_trace, script, payload, timeout)
        except subprocess.TimeoutExpired:
            return {"frames": [], "stdout": "", "error": f"Timeout after {timeout}s"}
        lines = proc.stdout.decode().strip().splitlines()
        if not lines:
            return {"frames": [], "stdout": "", "error": (proc.stderr.decode()[:500] or "Process error")}
        try:
            return json.loads(lines[-1])
        except ValueError:
            return {"frames": [], "stdout": "", "error": "Invalid trace output"}


def _run_trace(script: Path, payload: Path, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return _spawn([str(script), str(payload)], script.parent, timeout)


def _result(cases: list[dict], runtime_error: str | None, test_cases: list[dict]) -> dict:
    total = len(test_cases)
    if not cases:
        cases = [{"name": c["description"], "passed": False, "stdout": "", "error": runtime_error, "actual": None}
                 for c in test_cases]
    passed = sum(1 for c in cases if c["passed"])
    coverage = round(passed / total, 3) if total else 0.0
    return {"passed": passed, "total": total, "coverage": coverage, "cases": cases, "runtime_error": runtime_error}
