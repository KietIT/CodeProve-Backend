"""Play scripted student sessions through the CodeProve API (P1.3b golden set).

Each script is one simulated student working one exercise, as the web client
would: the same endpoints and the same client telemetry (OPEN, CODE_EDIT,
TAB_HIDDEN, ...). Everything behind the API is real: sandbox, Ciel (planted
bug included), the hypothesis and explain-back judges, and the scoring engine.

    python -m app.features.calibration.simulate check --scripts DIR
    python -m app.features.calibration.simulate profile-mutants [--out FILE]
    python -m app.features.calibration.simulate run --api URL --scripts DIR --state FILE [--only ID] [--speed 1]
    python -m app.features.calibration.simulate answer --api URL --state FILE --answers FILE

`run` stops each session after Submit and stores the generated explain-back
questions in the state file; `answer` posts the answers written for them and
records the engine's result. Steps run in real time (`at` = minutes after the
attempt opens) so the timestamps the server writes stay realistic.
"""
import argparse
import asyncio
import json
import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.exercises.starters import student_starter
from app.features.scoring.evidence import code_blocks
from app.seed.exercises_seed import EXERCISES

logger = logging.getLogger(__name__)

EMAIL = "calib.sim{:02d}@example.com"
_MUTANT_REF = re.compile(r"^mutant:(\d+)$")
_ENTRY = re.compile(r"^(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)
_RATE_LIMIT_RETRIES = 4


# ---------- Scripts ----------

class Step(BaseModel):
    at: float = Field(ge=0, le=45, description="minutes after the attempt opens")
    do: Literal["hypothesis", "code", "run", "ask", "use_ai_code", "away", "submit"]
    text: str | None = None
    ref: str | None = None  # starter | reference | mutant:N | inline
    code: str | None = None
    send_code: bool = False
    seconds: int = Field(default=30, ge=1, le=600)
    kind: Literal["tab", "window"] = "tab"

    @model_validator(mode="after")
    def _fields_for_action(self) -> "Step":
        if self.do in ("hypothesis", "ask") and not (self.text and self.text.strip()):
            raise ValueError(f"'{self.do}' needs text")
        if self.do == "code":
            if not self.ref:
                raise ValueError("'code' needs a ref")
            if self.ref == "inline" and self.code is None:
                raise ValueError("ref 'inline' needs code")
        return self


class Script(BaseModel):
    id: str = Field(pattern=r"^sim-\d{2}$")
    student: int = Field(ge=1, le=99)
    exercise: str = Field(pattern=r"^CP-\d{3}$")
    locale: Literal["vi", "en"] = "vi"
    steps: list[Step] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def _ends_with_one_submit(cls, steps: list[Step]) -> list[Step]:
        steps = sorted(steps, key=lambda s: s.at)
        if steps[-1].do != "submit" or sum(s.do == "submit" for s in steps) != 1:
            raise ValueError("a script needs exactly one submit, as its last step")
        return steps


@dataclass(frozen=True)
class Material:
    """What a student can type: the starter they see, the reference and the mutants."""

    code: str
    kind: str
    starter: str
    reference: str
    mutants: tuple[str, ...]
    entry: str


def load_material(code: str, content_dir: Path = CONTENT_DIR) -> Material:
    content = load_content_file(content_dir / f"{code}.json")
    seed = next(e for e in EXERCISES if e["code"] == code)
    kind = seed.get("kind") or "implement"
    match = _ENTRY.search(content.reference_solution)
    return Material(
        code=code,
        kind=kind,
        starter=student_starter(content.starter_for(seed["starter_code"]), kind),
        reference=content.reference_solution,
        mutants=tuple(m.code for m in content.mutants),
        entry=match.group(1) if match else "",
    )


def resolve_code(step: Step, material: Material) -> str:
    if step.ref == "starter":
        return material.starter
    if step.ref == "reference":
        return material.reference
    if step.ref == "inline":
        return step.code or ""
    match = _MUTANT_REF.match(step.ref or "")
    if match and 1 <= int(match.group(1)) <= len(material.mutants):
        return material.mutants[int(match.group(1)) - 1]
    raise ValueError(f"cannot resolve ref {step.ref!r}")


def validate_script(script: Script, material: Material) -> list[str]:
    errors = []
    for i, step in enumerate(script.steps, start=1):
        if step.do != "code" or step.ref in ("starter", "reference", "inline"):
            continue
        match = _MUTANT_REF.match(step.ref or "")
        if not match:
            errors.append(f"step {i}: unknown ref {step.ref!r}")
        elif not 1 <= int(match.group(1)) <= len(material.mutants):
            errors.append(f"step {i}: {step.ref} out of range (1-{len(material.mutants)})")
    return errors


def load_scripts(directory: Path) -> list[Script]:
    return [Script.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("sim-*.json"))]


def ai_code(reply: str, entry: str) -> str | None:
    """The largest code block of a Ciel reply that defines the exercise's entry point."""
    blocks = code_blocks(reply)
    usable = [b for b in blocks if entry and re.search(rf"^\s*(?:def|class)\s+{re.escape(entry)}\b", b, re.MULTILINE)]
    return max(usable, key=len) if usable else None


def chars_added(old: str, new: str) -> int:
    """Characters typed to turn `old` into `new` (what the editor's CODE_EDIT counts)."""
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(len(old), len(new)) - prefix and old[-1 - suffix] == new[-1 - suffix]:
        suffix += 1
    return max(1, len(new) - prefix - suffix)


# ---------- API ----------

class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status


class Api:
    def __init__(self, client: httpx.AsyncClient, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._client = client
        self._sleep = sleep

    async def call(self, method: str, path: str, token: str | None = None, body: dict | None = None,
                   params: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            res = await self._client.request(method, f"/api{path}", json=body, params=params, headers=headers)
            if res.status_code == 429 and attempt < _RATE_LIMIT_RETRIES:
                await self._sleep(float(res.headers.get("Retry-After", 15)))
                continue
            if res.status_code >= 400:
                try:
                    detail = res.json().get("detail", res.text)
                except ValueError:
                    detail = res.text
                raise ApiError(res.status_code, str(detail))
            return res.json()
        raise AssertionError("unreachable")

    async def token_for(self, student: dict) -> str:
        try:
            out = await self.call("POST", "/auth/signup", body={
                "full_name": student["name"], "email": student["email"], "password": student["password"]})
        except ApiError as exc:
            if exc.status != 409:
                raise
            out = await self.call("POST", "/auth/login", body={
                "email": student["email"], "password": student["password"]})
        return out["access_token"]


# ---------- State ----------

class State:
    """JSON file shared by both phases: accounts, attempts, questions, results."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"students": {}, "sessions": {}}

    def student(self, n: int) -> dict:
        key = str(n)
        if key not in self.data["students"]:
            self.data["students"][key] = {
                "name": f"Sim {n:02d}", "email": EMAIL.format(n), "password": secrets.token_urlsafe(18)}
            self.save()
        return self.data["students"][key]

    def session(self, script_id: str) -> dict:
        return self.data["sessions"].setdefault(script_id, {"status": "new"})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


# ---------- Player ----------

@dataclass
class Player:
    script: Script
    material: Material
    api: Api
    state: State
    log: Callable[[dict], None]
    speed: float = 1.0
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    now_ms: Callable[[], int] = lambda: int(time.time() * 1000)
    monotonic: Callable[[], float] = time.monotonic
    token: str | None = None  # signed in beforehand when several scripts share a student

    code: str = ""
    snapshots: int = 0  # mirrors the server's snapshot count, so versions stay in order
    last_reply: str = ""
    questions: list[str] | None = None

    async def play(self) -> None:
        record = self.state.session(self.script.id)
        if record["status"] in ("submitted", "scored"):
            return
        token = self.token or await self.api.token_for(self.state.student(self.script.student))
        attempt = await self.api.call("POST", "/attempts", token, {"exercise_code": self.script.exercise})
        attempt_id = attempt["attempt_id"]
        record.update(status="in_progress", attempt_id=attempt_id, student=self.script.student,
                      exercise=self.script.exercise, error=None)
        self.state.save()
        self.code = self.material.starter
        started = self.monotonic()
        await self._events(token, attempt_id, [self._event("OPEN")])
        for i, step in enumerate(self.script.steps, start=1):
            wait = step.at * 60 / self.speed - (self.monotonic() - started)
            if wait > 0:
                await self.sleep(wait)
            out = await self._do(step, token, attempt_id)
            self.log({"step": i, "do": step.do, **out})
        record.update(status="submitted", questions=self.questions)
        self.state.save()

    def _event(self, type_: str, payload: dict | None = None, flags: list[str] | None = None) -> dict:
        return {"type": type_, "ts": self.now_ms(), "payload": payload or {}, "integrity_flags": flags or []}

    async def _events(self, token: str, attempt_id: int, events: list[dict]) -> None:
        await self.api.call("POST", f"/attempts/{attempt_id}/events", token, {"events": events})

    async def _type_code(self, token: str, attempt_id: int, new: str) -> dict:
        if new == self.code:
            return {"changed": False}
        added = chars_added(self.code, new)
        await self._events(token, attempt_id, [self._event("CODE_EDIT", {"charsAdded": added})])
        self.code = new
        self.snapshots += 1
        await self.api.call("POST", f"/attempts/{attempt_id}/snapshots", token,
                            {"version": self.snapshots, "source_code": new})
        return {"changed": True, "chars_added": added}

    async def _do(self, step: Step, token: str, attempt_id: int) -> dict:
        base = f"/attempts/{attempt_id}"
        if step.do == "hypothesis":
            out = await self.api.call("POST", f"{base}/hypothesis", token, {"text": step.text})
            return {"text": step.text, **out}
        if step.do == "code":
            return {"ref": step.ref, **await self._type_code(token, attempt_id, resolve_code(step, self.material))}
        if step.do == "run":
            out = await self.api.call("POST", f"{base}/run", token, {"source_code": self.code, "run_tests": True})
            self.snapshots += 1  # /run stores the code as the next snapshot version
            return {"passed": out.get("passed"), "total": out.get("total"), "runtime_error": out.get("runtime_error")}
        if step.do == "ask":
            body = {"message": step.text, "code": self.code if step.send_code else None}
            out = await self.api.call("POST", f"{base}/mentor", token, body)
            self.last_reply = out.get("reply", "")
            return {"text": step.text, "reply": self.last_reply}
        if step.do == "use_ai_code":
            snippet = ai_code(self.last_reply, self.material.entry)
            if snippet is None:
                return {"adopted": False}
            return {"adopted": True, **await self._type_code(token, attempt_id, snippet)}
        if step.do == "away":
            hidden, back = ("TAB_HIDDEN", "TAB_VISIBLE") if step.kind == "tab" else ("WINDOW_BLUR", "WINDOW_FOCUS")
            await self._events(token, attempt_id, [self._event(hidden, flags=[hidden])])
            await self.sleep(step.seconds / self.speed)
            await self._events(token, attempt_id, [self._event(back, {"awayMs": step.seconds * 1000})])
            return {"kind": step.kind, "seconds": step.seconds}
        if step.do == "submit":
            out = await self.api.call("POST", f"{base}/submit", token, params={"locale": self.script.locale})
            self.questions = out.get("questions", [])
            return {"questions": self.questions, "tests": out.get("tests")}
        raise ValueError(step.do)


async def answer_all(api: Api, state: State, answers: dict[str, list[str]], only: str | None = None) -> list[str]:
    """Phase 2: post each submitted session's explain-back answers. Returns the ids that failed."""
    failed = []
    for script_id, record in sorted(state.data["sessions"].items()):
        if record.get("status") != "submitted" or (only and script_id != only):
            continue
        questions, replies = record.get("questions") or [], answers.get(script_id)
        if not replies or len(replies) != len(questions):
            logger.error("%s: need %d answer(s), got %s", script_id, len(questions), len(replies or []))
            failed.append(script_id)
            continue
        try:
            token = await api.token_for(state.student(record["student"]))
            out = await api.call("POST", f"/attempts/{record['attempt_id']}/explain-back", token, {
                "answers": [{"question": q, "answer": a} for q, a in zip(questions, replies)]})
        except ApiError as exc:
            logger.error("%s: %s", script_id, exc)
            failed.append(script_id)
            continue
        record.update(status="scored", answers=replies, result={
            "overall": out["overall"], "tier": out["tier"], "axes": out["axes"],
            "not_applicable": out["feedback"].get("not_applicable", {})})
        state.save()
    return failed


# ---------- Mutant profile ----------

async def profile_mutants(content_dir: Path = CONTENT_DIR, timeout: int = 5) -> dict[str, list[dict]]:
    """Per exercise, how the starter and each mutant fare on visible and hidden tests."""
    from app.features.sandbox.runner import run_tests

    out: dict[str, list[dict]] = {}
    for path in sorted(content_dir.glob("CP-*.json")):
        content = load_content_file(path)
        material = load_material(content.code, content_dir)
        split = {
            hidden: [{"input_data": t.input, "expected_output": t.expected, "description": t.description,
                      "weight": 1.0} for t in content.tests if t.hidden == hidden]
            for hidden in (False, True)
        }
        rows = []
        for label, code in [("starter", material.starter)] + [
                (f"mutant:{i}", m) for i, m in enumerate(material.mutants, start=1)]:
            vis = await run_tests(code, split[False], timeout)
            hid = await run_tests(code, split[True], timeout)
            rows.append({"ref": label, "visible": f"{vis['passed']}/{vis['total']}",
                         "hidden": f"{hid['passed']}/{hid['total']}"})
        out[content.code] = rows
    return out


# ---------- CLI ----------

def _jsonl_logger(directory: Path, script_id: str) -> Callable[[dict], None]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{script_id}.jsonl"

    def write(entry: dict) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), **entry}, ensure_ascii=False) + "\n")
    return write


async def _run(api_url: str, scripts: list[Script], state: State, logs: Path, speed: float) -> list[str]:
    async with httpx.AsyncClient(base_url=api_url, timeout=120) as client:
        api = Api(client)
        # Sign each student in once, one at a time: two scripts of one student signing up
        # concurrently race on the unique email (the server answers 500, not 409).
        tokens = {}
        for n in sorted({s.student for s in scripts}):
            tokens[n] = await api.token_for(state.student(n))

        async def one(script: Script) -> str | None:
            log = _jsonl_logger(logs, script.id)
            player = Player(script, load_material(script.exercise), api, state, log, speed,
                            token=tokens[script.student])
            try:
                await player.play()
            except Exception as exc:  # one broken session must not stop the others
                logger.exception("%s failed", script.id)
                log({"error": str(exc)})
                state.session(script.id).update(status="failed", error=str(exc))
                state.save()
                return script.id
            return None

        results = await asyncio.gather(*(one(s) for s in scripts))
    return [r for r in results if r]


async def _answer(api_url: str, state: State, answers: dict, only: str | None) -> list[str]:
    async with httpx.AsyncClient(base_url=api_url, timeout=120) as client:
        return await answer_all(Api(client), state, answers, only)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("--scripts", type=Path, required=True)
    prof = sub.add_parser("profile-mutants")
    prof.add_argument("--out", type=Path)
    run = sub.add_parser("run")
    run.add_argument("--api", required=True)
    run.add_argument("--scripts", type=Path, required=True)
    run.add_argument("--state", type=Path, required=True)
    run.add_argument("--only", action="append")
    run.add_argument("--speed", type=float, default=1.0)
    ans = sub.add_parser("answer")
    ans.add_argument("--api", required=True)
    ans.add_argument("--state", type=Path, required=True)
    ans.add_argument("--answers", type=Path, required=True)
    ans.add_argument("--only")
    args = parser.parse_args()

    if args.cmd == "check":
        problems = 0
        for s in load_scripts(args.scripts):
            for err in validate_script(s, load_material(s.exercise)):
                problems += 1
                print(f"{s.id}: {err}")
        print("ok" if not problems else f"{problems} problem(s)")
        raise SystemExit(1 if problems else 0)
    if args.cmd == "profile-mutants":
        result = asyncio.run(profile_mutants())
        for code, rows in result.items():
            print(code, "  ".join(f"{r['ref']} v{r['visible']} h{r['hidden']}" for r in rows))
        if args.out:
            args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return
    if args.cmd == "run":
        scripts = [s for s in load_scripts(args.scripts) if not args.only or s.id in args.only]
        failed = asyncio.run(_run(args.api.rstrip("/"), scripts, State(args.state),
                                  args.state.parent / "logs", args.speed))
        print(f"{len(scripts) - len(failed)} submitted, failed: {failed or 'none'}")
        return
    answers = json.loads(args.answers.read_text(encoding="utf-8"))
    failed = asyncio.run(_answer(args.api.rstrip("/"), State(args.state), answers, args.only))
    print(f"failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
