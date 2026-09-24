# P0 Scoring Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop the scoring engine from punishing students for skills they had no opportunity to show, close the obvious gaming paths, stop leaking answers/traps, and rescore existing reports.

**Architecture:** An axis the session gave no opportunity to observe returns `None` ("not applicable") with a reason code; `overall` already renormalises over non-`None` axes. The `/run` endpoint records whether the run was the untouched starter and the pass ratio, so Debugging can ignore farmed failures and Testing no longer depends on how many cases the author wrote. A one-off `rescore` command recomputes stored reports from their events. The frontend shows N/A axes with their reason instead of "0".

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Alembic, pytest (+ aiosqlite); Next.js 14 / TypeScript, `node --test`.

**Roadmap:** `docs/superpowers/specs/2026-09-24-scoring-roadmap.md` (this is phase P0).

---

## Decisions (agreed with the product owner)

1. **Prompting** is N/A when the student never prompted Ciel. **Verification** is N/A when no Ciel reply contained code and no trap was injected (nothing to verify).
2. **Debugging** is scored on implement exercises only after a real failing run of the student's own code; a first-try pass is N/A. Debug-kind exercises are always applicable (the starter is broken by design).
3. **Existing reports are rescored** with the new engine.

## Interim formulas (P0 only; P1 replaces them with evidence-centred rubrics)

| Axis | Applicable when | Score (0–20) |
|---|---|---|
| Debugging, implement | ≥1 failing run of non-starter code before the first pass | never passed → 0; else `16 − 2·(fails − 1)`, clamped to 10–16 |
| Debugging, debug-kind | always | never passed → 0; else `20 − 2·fails`, clamped to 12–20 |
| Prompting | ≥1 prompt | unchanged formula |
| Verification | AI reply with code, or trap injected | `20·earned/possible − penalties`, earned = 12 (trap caught) + 8 (ran code after first AI code), possible = 8 (+12 if trap) |
| Testing | always | `20 × pass ratio of the last run` (0 if never ran) |

Implement-kind Debugging tops out at 16 so that, other things equal, needing fixes never beats a clean first-try solve. Runs after the first pass are ignored, so toggling pass/fail cannot farm the axis.

**Known limitation (fixed in P2):** a student can still write deliberately wrong code, run it, then fix it, to earn implement-kind Debugging (max 16).

## Repos and branches

- Backend: `codeprove-backend`, worktree `.claude/worktrees/ai-scoring-feedback-issues-f1bc15`, branch `claude/ai-scoring-feedback-issues-f1bc15` (already fast-forwarded to `origin/main`).
- Frontend: `codeprove-web`. Create a fresh worktree from `origin/main` (Task 11). Do **not** reuse other sessions' worktrees.
- Backend test command (the venv lives in the main checkout): `../../../.venv/Scripts/python.exe -m pytest -q` from the worktree root. Baseline: **122 passed, 2 skipped**.

---

### Task 1: Code helpers — strip comments, detect untouched starter

**Files:**
- Modify: `app/features/exercises/starters.py`
- Test: `tests/test_exercise_starters.py`

**Step 1: Write the failing tests** (append to `tests/test_exercise_starters.py`)

```python
from app.features.exercises.starters import is_untouched, strip_comments, student_starter


def test_strip_comments_removes_inline_and_full_line_comments() -> None:
    src = (
        "def sum_to_n(n):\n"
        "    # accumulate\n"
        "    total = 0\n"
        "    for i in range(1, n):   # bug: never adds n itself\n"
        "        total += i\n"
        "    return total"
    )
    assert strip_comments(src) == (
        "def sum_to_n(n):\n"
        "    total = 0\n"
        "    for i in range(1, n):\n"
        "        total += i\n"
        "    return total"
    )


def test_strip_comments_keeps_hash_inside_strings() -> None:
    src = 'def tag():\n    return "#not-a-comment"  # real comment'
    assert strip_comments(src) == 'def tag():\n    return "#not-a-comment"'


def test_strip_comments_returns_source_unchanged_when_untokenizable() -> None:
    src = "def broken(:\n    x = (1,"
    assert strip_comments(src) == src


def test_student_starter_strips_comments_for_debug_and_body_for_implement() -> None:
    buggy = "def f(n):\n    return n - 1  # bug: should be n + 1"
    assert student_starter(buggy, "debug") == "def f(n):\n    return n - 1"
    assert student_starter("def f(n):\n    return n + 1", "implement") == "def f(n):\n    pass"


def test_is_untouched_ignores_whitespace_and_detects_empty_editor() -> None:
    starter = "def f(n):\n    pass"
    assert is_untouched("def f(n):\n    pass\n\n", starter) is True
    assert is_untouched("def f(n):   \r\n    pass", starter) is True
    assert is_untouched("   \n", starter) is True
    assert is_untouched("def f(n):\n    return n", starter) is False
```

**Step 2: Run to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_exercise_starters.py -q`
Expected: FAIL with `ImportError: cannot import name 'is_untouched'`

**Step 3: Implement** (append to `app/features/exercises/starters.py`; add `import io` and `import tokenize` to the imports at the top)

```python
def strip_comments(source: str) -> str:
    """Remove `#` comments so a starter cannot leak the bug it contains.

    Uses the tokenizer, so a '#' inside a string literal is kept. A line that
    held only a comment is dropped. Source that cannot be tokenized is
    returned unchanged rather than half-stripped.
    """
    source = source.replace("\r\n", "\n")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source
    comment_col = {t.start[0]: t.start[1] for t in tokens if t.type == tokenize.COMMENT}
    if not comment_col:
        return source
    out: list[str] = []
    for lineno, line in enumerate(source.split("\n"), start=1):
        col = comment_col.get(lineno)
        if col is None:
            out.append(line)
            continue
        kept = line[:col].rstrip()
        if kept:
            out.append(kept)
    return "\n".join(out)


def student_starter(starter_code: str, kind: str) -> str:
    """The starter exactly as the student sees it in the editor."""
    return strip_comments(starter_code) if kind == "debug" else student_safe_starter(starter_code)


def normalize_code(source: str) -> str:
    lines = (line.rstrip() for line in source.replace("\r\n", "\n").split("\n"))
    return "\n".join(line for line in lines if line)


def is_untouched(source: str, starter: str) -> bool:
    """True for an empty editor or the unmodified starter (whitespace-insensitive)."""
    code = normalize_code(source)
    return code == "" or code == normalize_code(starter)
```

**Step 4: Run to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_exercise_starters.py -q`
Expected: all PASS

**Step 5: Commit**

```bash
git add app/features/exercises/starters.py tests/test_exercise_starters.py
git commit -m "feat(exercises): add comment stripping and untouched-starter detection"
```

---

### Task 2: Serve debug starters without answer-leaking comments

Seven debug starters carry comments that give the bug away (e.g. `# bug: never adds n itself`, `# read-modify-write is not atomic`, `# vulnerable: string concatenation`). The seed script is insert-only, so editing the seed would not change the production DB: strip at serve time instead.

**Files:**
- Modify: `app/features/exercises/service.py` (the `starter = ...` line in `get_detail`)
- Test: `tests/test_exercises.py` (`test_detail_starter_stripped_for_implement_kept_for_debug`)

**Step 1: Update the failing test.** Replace the last assertion of `test_detail_starter_stripped_for_implement_kept_for_debug`:

```python
    debug = (await client.get("/api/exercises/CP-902", headers=auth_headers)).json()
    assert debug["kind"] == "debug"
    # Buggy body shown, but the comment that names the bug is stripped.
    assert "range(1, n)" in debug["starter"]
    assert "#" not in debug["starter"]
```

**Step 2: Run to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_exercises.py -q`
Expected: FAIL on `assert "#" not in debug["starter"]`

**Step 3: Implement.** In `app/features/exercises/service.py` change the import to `from app.features.exercises.starters import student_starter` and replace:

```python
    starter = ex.starter_code if ex.kind == "debug" else student_safe_starter(ex.starter_code)
```

with:

```python
    starter = student_starter(ex.starter_code, ex.kind)
```

(Keep the comment above it but update it: "Debug-type starters keep the buggy body but lose comments, which often name the bug; implement-type starters are stripped to a scaffold.")

**Step 4: Run to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_exercises.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add app/features/exercises/service.py tests/test_exercises.py
git commit -m "fix(exercises): strip answer-leaking comments from debug starters"
```

---

### Task 3: Record `isStarter` and `passRatio` on every run

**Files:**
- Modify: `app/features/attempts/router.py` (`run` endpoint, ~lines 56–79)
- Create: `tests/test_run_telemetry.py`

**Step 1: Write the failing test** (`tests/test_run_telemetry.py`). This runs the real subprocess sandbox, like `tests/test_sandbox.py`.

```python
import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def _attempt(client, db_session, auth_headers) -> int:
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-950", title="Double", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", summary="double x", kind="implement",
                  starter_code="def double(x):\n    return x * 2", hint="", domain_keywords=[])
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="double(2)", expected_output="4",
                            description="t1", is_hidden=False, order_index=1))
    db_session.add(TestCase(exercise_id=ex.id, input_data="double(0)", expected_output="0",
                            description="t2", is_hidden=False, order_index=2))
    await db_session.commit()
    r = await client.post("/api/attempts", json={"exercise_code": "CP-950"}, headers=auth_headers)
    return r.json()["attempt_id"]


async def _run_events(db_session, aid):
    from app.models import Event

    rows = (await db_session.execute(
        select(Event).where(Event.attempt_id == aid, Event.type == "RUN").order_by(Event.id)
    )).scalars().all()
    return [r.payload for r in rows]


async def test_run_records_starter_flag_and_pass_ratio(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    # 1) untouched starter (the scaffold the student sees is "def double(x):\n    pass")
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    pass\n", "run_tests": True})
    # 2) half-right code: passes double(0) only
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    return x * 3", "run_tests": True})
    # 3) correct
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    return x + x", "run_tests": True})

    payloads = await _run_events(db_session, aid)
    assert [p["isStarter"] for p in payloads] == [True, False, False]
    assert [p["passRatio"] for p in payloads] == [0.0, 0.5, 1.0]
    assert [p["passed"] for p in payloads] == [False, False, True]
```

**Step 2: Run to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_run_telemetry.py -q`
Expected: FAIL with `KeyError: 'isStarter'`

**Step 3: Implement.** In `app/features/attempts/router.py` add the import `from app.features.exercises.starters import is_untouched, student_starter`. In `run`, after `attempt = await service.require_attempt(...)`, load the exercise:

```python
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
```

and replace the `RUN` event line with:

```python
    pass_ratio = round(result["passed"] / result["total"], 3) if result["total"] else 0.0
    # isStarter: running the untouched scaffold (or an empty editor) is not a real
    # attempt, so scoring must not count its failure as something "debugged".
    await service.add_event(db, attempt_id, "RUN", {
        "passed": all_passed,
        "passRatio": pass_ratio,
        "isStarter": is_untouched(data.source_code, student_starter(ex.starter_code, ex.kind)),
    })
```

Leave the `TEST_RUN` event unchanged.

**Step 4: Run to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_run_telemetry.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add app/features/attempts/router.py tests/test_run_telemetry.py
git commit -m "feat(attempts): record starter flag and pass ratio on each run"
```

---

### Task 4: New features — runs, real failures, AI-code verification

**Files:**
- Modify: `app/features/scoring/features.py` (full replacement below)
- Test: `tests/test_features.py`

**Step 1: Update and add tests** in `tests/test_features.py`:

- In `test_hypothesis_and_debugging_features` replace `assert f.d1_count == 1` with:
  ```python
      assert f.real_fails_before_first_pass == 1   # the RUN at 300 failed before the pass at 400
      assert f.any_pass is True
  ```
- In `test_features_are_timestamp_ordered_not_list_ordered` replace `assert f.d1_count == 1` with `assert f.real_fails_before_first_pass == 1`.
- Replace `test_testing_features` with:
  ```python
  def test_testing_features_use_last_run_pass_ratio():
      events = [
          _ev("OPEN", 0),
          _ev("TEST_RUN", 100, {"passed": False, "testCount": 4, "coverage": 0.5}),
          _ev("TEST_RUN", 200, {"passed": True, "testCount": 4, "coverage": 0.85}),
      ]
      f = compute_features(events, explain_score=0.0)
      assert f.has_test_run is True
      assert f.best_coverage == 0.85
      assert f.run_count == 2                 # legacy session: TEST_RUN is the run stream
      assert f.final_pass_ratio == 0.85
  ```
- Append:
  ```python
  def test_run_is_the_run_stream_and_test_run_duplicates_are_ignored():
      events = [
          _ev("RUN", 100, {"passed": False, "passRatio": 0.5, "isStarter": False}),
          _ev("TEST_RUN", 100, {"passed": False, "testCount": 2, "coverage": 0.5}),
          _ev("RUN", 200, {"passed": True, "passRatio": 1.0, "isStarter": False}),
          _ev("TEST_RUN", 200, {"passed": True, "testCount": 2, "coverage": 1.0}),
      ]
      f = compute_features(events, explain_score=0.0)
      assert f.run_count == 2
      assert f.real_fails_before_first_pass == 1
      assert f.final_pass_ratio == 1.0


  def test_starter_runs_and_runs_after_first_pass_are_not_real_failures():
      events = [
          _ev("RUN", 100, {"passed": False, "passRatio": 0.0, "isStarter": True}),   # untouched scaffold
          _ev("RUN", 200, {"passed": True, "passRatio": 1.0, "isStarter": False}),
          _ev("RUN", 300, {"passed": False, "passRatio": 0.0, "isStarter": False}),  # regression after solving
          _ev("RUN", 400, {"passed": True, "passRatio": 1.0, "isStarter": False}),
      ]
      f = compute_features(events, explain_score=0.0)
      assert f.real_fails_before_first_pass == 0


  def test_ai_code_and_testing_after_it():
      events = [
          _ev("PROMPT", 100, {"messageLength": 60, "messageText": "how do I handle an empty list edge case?"}),
          _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": [{"loc": 4}]}),
          _ev("RUN", 300, {"passed": True, "passRatio": 1.0, "isStarter": False}),
      ]
      f = compute_features(events, explain_score=0.0)
      assert f.ai_code_received is True
      assert f.tested_after_ai_code is True
      assert f.trap_injected is False


  def test_text_only_ai_reply_is_not_ai_code():
      events = [
          _ev("PROMPT", 100, {"messageLength": 60, "messageText": "what does this problem ask?"}),
          _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": []}),
      ]
      f = compute_features(events, explain_score=0.0)
      assert f.ai_code_received is False
      assert f.tested_after_ai_code is False
  ```

**Step 2: Run to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_features.py -q`
Expected: FAIL with `AttributeError: 'AxisFeatures' object has no attribute 'real_fails_before_first_pass'`

**Step 3: Replace `app/features/scoring/features.py`** with:

```python
from dataclasses import dataclass, field

from app.features.scoring.text_utils import cluster_near_duplicates

_CONSTRAINT_HINTS = (
    "return", "format", "complexity", "o(", "constraint", "edge", "must", "should",
    "ràng buộc", "định dạng",
)


@dataclass
class AxisFeatures:
    first_prompt_delay_ms: int | None = None
    problem_read_ratio: float = 1.0
    u2_hits: int = 0
    explain_score: float = 0.0
    h1_count: int = 0
    h2_count: int = 0
    hypothesis_count: int = 0
    has_hypothesis_before_code: bool = False
    code_edits: int = 0
    chars_added: int = 0
    p1_hits: int = 0
    p1_ratio: float = 0.0
    p2_clusters: int = 0
    p3_hits: int = 0
    p4_hits: int = 0
    prompt_count: int = 0
    trap_injected: bool = False
    has_v1: bool = False
    has_v1b: bool = False
    v2_count: int = 0
    has_v3: bool = False
    ai_code_received: bool = False
    tested_after_ai_code: bool = False
    best_coverage: float = 0.0
    has_test_run: bool = False
    run_count: int = 0
    final_pass_ratio: float = 0.0
    any_pass: bool = False
    real_fails_before_first_pass: int = 0
    paste_flags: int = 0
    focus_lost: int = 0
    tab_hidden: int = 0
    window_blur: int = 0
    fullscreen_exits: int = 0
    copy_count: int = 0
    cut_count: int = 0
    paste_count: int = 0
    integrity_flag_total: int = field(default=0)


def _ai_loc(reply: dict) -> int:
    return sum(c.get("loc", 0) for c in reply["payload"].get("aiCode", []))


def _pass_ratio(payload: dict) -> float:
    if "passRatio" in payload:
        return float(payload["passRatio"])
    if "coverage" in payload:  # legacy TEST_RUN: "coverage" was the pass ratio
        return float(payload["coverage"])
    return 1.0 if payload.get("passed") else 0.0


def compute_features(events: list[dict], explain_score: float | None) -> AxisFeatures:
    f = AxisFeatures(explain_score=explain_score or 0.0)
    # Work on a timestamp-ordered copy so every "first"/transition derivation is
    # order-robust regardless of append order (pure: the input list is not mutated).
    events = sorted(events, key=lambda e: e["ts"])
    open_ts = next((e["ts"] for e in events if e["type"] == "OPEN"), None)
    first_prompt = next((e for e in events if e["type"] == "PROMPT"), None)
    first_code = next((e for e in events if e["type"] == "CODE_EDIT"), None)
    # Every /run call logs one RUN (plus a duplicate TEST_RUN when tests are run),
    # so RUN is the one-event-per-execution stream. Sessions that only logged
    # TEST_RUN fall back to it.
    runs = [e for e in events if e["type"] == "RUN"] or [e for e in events if e["type"] == "TEST_RUN"]

    if open_ts is not None and first_prompt is not None:
        f.first_prompt_delay_ms = first_prompt["ts"] - open_ts
    open_ev = next((e for e in events if e["type"] == "OPEN"), None)
    if open_ev:
        f.problem_read_ratio = float(open_ev["payload"].get("problemReadRatio", 1.0))

    prompts = [e for e in events if e["type"] == "PROMPT"]
    f.prompt_count = len(prompts)
    prompt_texts = [e["payload"].get("messageText", "") for e in prompts]
    for e in prompts:
        ml = int(e["payload"].get("messageLength", 0))
        kw = e["payload"].get("keywordsMatched", []) or []
        if 0 < ml < 30:
            f.p1_hits += 1
        if len(kw) >= 2:
            f.p3_hits += 1
        if not any(h in e["payload"].get("messageText", "").lower() for h in _CONSTRAINT_HINTS):
            f.p4_hits += 1
    f.p1_ratio = (f.p1_hits / f.prompt_count) if f.prompt_count else 0.0
    f.p3_hits = min(f.p3_hits, 4)  # +2 each, capped at +8
    f.p2_clusters = cluster_near_duplicates(prompt_texts, 0.85)

    # U2: AI replies to shallow concept prompts (short message, no matched keywords).
    replies = [e for e in events if e["type"] == "AI_REPLY"]
    f.u2_hits = min(
        sum(
            1
            for p in prompts
            if int(p["payload"].get("messageLength", 0)) < 40 and not (p["payload"].get("keywordsMatched"))
        ),
        4,
    )

    # Real-work signals: how much code the student actually typed.
    code_edits = [e for e in events if e["type"] == "CODE_EDIT"]
    f.code_edits = len(code_edits)
    f.chars_added = sum(int(e["payload"].get("charsAdded", 0)) for e in code_edits)

    # Hypothesis
    hyps = [e for e in events if e["type"] == "HYPOTHESIS"]
    f.hypothesis_count = len(hyps)
    f.h1_count = sum(1 for e in hyps if e["payload"].get("proposedBy") == "user" and e["payload"].get("correct"))
    f.h2_count = sum(1 for e in hyps if e["payload"].get("proposedBy") == "ai")
    if hyps and first_code:
        f.has_hypothesis_before_code = any(h["ts"] < first_code["ts"] for h in hyps)
    elif hyps and not first_code:
        f.has_hypothesis_before_code = True

    # Verification: trap caught/missed, speed-accept, paste-blind, testing AI code
    submit_ts = next((e["ts"] for e in events if e["type"] == "SUBMIT"), None)
    injected = [e for e in replies if e["payload"].get("injectedError")]
    f.trap_injected = bool(injected)
    if injected:
        trap_ts = injected[0]["ts"]
        edited_after = any(
            e["type"] == "CODE_EDIT" and e["ts"] > trap_ts and (submit_ts is None or e["ts"] <= submit_ts)
            for e in events
        )
        f.has_v1 = edited_after
        f.has_v1b = not edited_after
    # V2 speed-accept: an AI reply with >=20 loc followed by the next event within 15s.
    for i, e in enumerate(events):
        if e["type"] == "AI_REPLY":
            if _ai_loc(e) >= 20 and i + 1 < len(events) and (events[i + 1]["ts"] - e["ts"]) < 15000:
                f.v2_count += 1
    total_ai_loc = sum(_ai_loc(e) for e in replies)
    if total_ai_loc >= 50:
        # paste-blind if no CODE_EDIT follows the last AI reply
        last_reply_ts = max((e["ts"] for e in replies), default=None)
        f.has_v3 = last_reply_ts is not None and not any(
            e["type"] == "CODE_EDIT" and e["ts"] > last_reply_ts for e in events
        )
    # Verification needs something to verify: an AI reply that contained code.
    ai_code_replies = [e for e in replies if _ai_loc(e) > 0]
    f.ai_code_received = bool(ai_code_replies)
    if ai_code_replies:
        first_ai_code_ts = ai_code_replies[0]["ts"]
        f.tested_after_ai_code = any(r["ts"] > first_ai_code_ts for r in runs)

    # Testing
    test_runs = [e for e in events if e["type"] == "TEST_RUN"]
    f.has_test_run = len(test_runs) > 0
    f.best_coverage = max((float(e["payload"].get("coverage", 0.0)) for e in test_runs), default=0.0)
    f.run_count = len(runs)
    if runs:
        f.final_pass_ratio = _pass_ratio(runs[-1]["payload"])

    # Debugging: failing runs of the student's own code before the first pass.
    # Starter/empty runs cannot manufacture a failure, and anything after the
    # first pass is ignored, so toggling pass/fail cannot farm the axis.
    f.any_pass = any(bool(e["payload"].get("passed")) for e in runs)
    for e in runs:
        if e["payload"].get("passed"):
            break
        if not e["payload"].get("isStarter"):
            f.real_fails_before_first_pass += 1

    # Integrity raw signals. A PASTE_BLOCKED event means the student *tried* to
    # paste (e.g. an answer copied from another AI) and the editor prevented it -
    # that intent is as strong a signal as a burst paste, so it counts the same.
    # FOCUS_LOST is kept for legacy sessions; new sessions emit specific
    # tab/window/fullscreen events.
    f.paste_flags = sum(
        1
        for e in events
        if e["type"] == "BURST_PASTE"
        or "BURST_PASTE" in e.get("integrity_flags", [])
        or "PASTE_BLOCKED" in e.get("integrity_flags", [])
    )
    f.focus_lost = sum(1 for e in events if e["type"] == "FOCUS_LOST")
    f.tab_hidden = sum(1 for e in events if e["type"] == "TAB_HIDDEN")
    f.window_blur = sum(1 for e in events if e["type"] == "WINDOW_BLUR")
    f.fullscreen_exits = sum(1 for e in events if e["type"] == "FULLSCREEN_EXIT")
    f.copy_count = sum(1 for e in events if e["type"] == "COPY")
    f.cut_count = sum(1 for e in events if e["type"] == "CUT")
    f.paste_count = sum(1 for e in events if e["type"] == "PASTE")
    f.integrity_flag_total = (
        f.paste_flags
        + f.focus_lost
        + f.tab_hidden
        + f.window_blur
        + f.fullscreen_exits
    )
    return f
```

**Step 4: Run to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_features.py -q`
Expected: all PASS. (`tests/test_scoring_engine.py` may now fail; Task 5 fixes it.)

**Step 5: Commit**

```bash
git add app/features/scoring/features.py tests/test_features.py
git commit -m "feat(scoring): derive real failures, pass ratio and AI-code verification features"
```

---

### Task 5: Engine — N/A axes, anti-farm Debugging, interim Testing

**Files:**
- Modify: `app/features/scoring/engine.py` (full replacement below)
- Test: `tests/test_scoring_engine.py`

**Step 1: Update and add tests** in `tests/test_scoring_engine.py`:

- In `test_strong_attempt_scores_high`, update the two comments to the new rules: verification `# 12 (trap caught) + 8 (tested after AI code) of 20`, debugging `# implement: one real failure then fixed -> 16`. Assertions stay as they are.
- Replace `test_empty_attempt_scores_zero` with:
  ```python
  def test_empty_attempt_scores_zero():
      # Nothing done: every observable axis is 0, axes with no opportunity are N/A.
      events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
      res = score_attempt(events, explain_score=0.0)
      for axis in ("understanding", "hypothesis", "testing"):
          assert res["axes"][axis] == 0.0, f"{axis} should be 0 for an empty attempt"
      for axis in ("prompting", "verification", "debugging"):
          assert res["axes"][axis] is None, f"{axis} should be N/A for an empty attempt"
      assert res["overall"] == 0.0
  ```
- Replace `test_disabled_axes_renormalize` with:
  ```python
  def test_not_applicable_axes_renormalize():
      events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
      res = score_attempt(events, explain_score=20.0)
      assert res["axes"]["understanding"] == 18.0   # 0.9 * 20, no passing run
      assert res["not_applicable"] == {
          "prompting": "no_ai_use", "verification": "no_ai_code", "debugging": "no_failure",
      }
      # Active weights .25 (understanding) + .22 (hypothesis) + .10 (testing) = .57.
      assert res["overall"] == round(5 * (0.25 / 0.57) * 18.0, 2)
  ```
- Append:
  ```python
  def _solve(fails: int, kind_starter_runs: int = 0) -> list[dict]:
      """A good session (read the problem, correct hypothesis first) that needs
      `fails` real failing runs before passing; optional untouched-starter runs first."""
      ev = [_ev("OPEN", 0, {"problemReadRatio": 1.0}),
            _ev("HYPOTHESIS", 30000, {"proposedBy": "user", "correct": True}),
            _ev("CODE_EDIT", 60000, {"charsAdded": 200})]
      ts = 70000
      for _ in range(kind_starter_runs):
          ev.append(_ev("RUN", ts, {"passed": False, "passRatio": 0.0, "isStarter": True})); ts += 1000
      for _ in range(fails):
          ev.append(_ev("RUN", ts, {"passed": False, "passRatio": 0.5, "isStarter": False})); ts += 1000
      ev.append(_ev("RUN", ts, {"passed": True, "passRatio": 1.0, "isStarter": False}))
      ev.append(_ev("SUBMIT", ts + 1000, {}))
      return ev


  def test_first_try_solve_is_not_penalised_for_debugging():
      res = score_attempt(_solve(fails=0), explain_score=18.0)
      assert res["axes"]["debugging"] is None
      assert res["axes"]["prompting"] is None
      assert res["axes"]["verification"] is None
      assert res["axes"]["testing"] == 20.0
      assert res["overall"] > 85


  def test_needing_fixes_never_beats_a_clean_first_try():
      clean = score_attempt(_solve(fails=0), explain_score=18.0)
      one_fix = score_attempt(_solve(fails=1), explain_score=18.0)
      three_fixes = score_attempt(_solve(fails=3), explain_score=18.0)
      assert one_fix["axes"]["debugging"] == 16.0
      assert three_fixes["axes"]["debugging"] == 12.0
      assert clean["overall"] > one_fix["overall"] > three_fixes["overall"]


  def test_running_the_untouched_starter_cannot_farm_debugging():
      res = score_attempt(_solve(fails=0, kind_starter_runs=3), explain_score=18.0)
      assert res["axes"]["debugging"] is None


  def test_regression_after_first_pass_does_not_count():
      events = _solve(fails=0) + [
          _ev("RUN", 90000, {"passed": False, "passRatio": 0.5, "isStarter": False}),
          _ev("RUN", 91000, {"passed": True, "passRatio": 1.0, "isStarter": False}),
      ]
      assert score_attempt(events, explain_score=18.0)["axes"]["debugging"] is None


  def test_debug_exercise_always_scores_debugging():
      assert score_attempt(_solve(fails=0), 18.0, exercise_kind="debug")["axes"]["debugging"] == 20.0
      assert score_attempt(_solve(fails=1), 18.0, exercise_kind="debug")["axes"]["debugging"] == 18.0
      never_fixed = [_ev("OPEN", 0, {}), _ev("RUN", 1000, {"passed": False, "passRatio": 0.0, "isStarter": False})]
      assert score_attempt(never_fixed, 0.0, exercise_kind="debug")["axes"]["debugging"] == 0.0


  def test_testing_does_not_depend_on_how_many_cases_the_author_wrote():
      two = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0}), _ev("TEST_RUN", 100, {"passed": True, "testCount": 2, "coverage": 1.0})]
      five = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0}), _ev("TEST_RUN", 100, {"passed": True, "testCount": 5, "coverage": 1.0})]
      assert score_attempt(two, 0.0)["axes"]["testing"] == score_attempt(five, 0.0)["axes"]["testing"] == 20.0


  def test_verification_scores_testing_ai_code_and_the_trap():
      ai_code = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "edge case for empty input?"}),
                 _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": [{"loc": 5}]})]
      tested = ai_code + [_ev("RUN", 300, {"passed": True, "passRatio": 1.0})]
      assert score_attempt(tested, 0.0)["axes"]["verification"] == 20.0
      assert score_attempt(ai_code, 0.0)["axes"]["verification"] == 0.0

      trap = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "edge case for empty input?"}),
              _ev("AI_REPLY", 200, {"injectedError": True, "aiCode": [{"loc": 5}]})]
      caught = trap + [_ev("CODE_EDIT", 300, {"charsAdded": 5}), _ev("RUN", 400, {"passed": True, "passRatio": 1.0}),
                       _ev("SUBMIT", 500, {})]
      missed = trap + [_ev("RUN", 400, {"passed": True, "passRatio": 1.0}), _ev("SUBMIT", 500, {})]
      assert score_attempt(caught, 0.0)["axes"]["verification"] == 20.0
      assert score_attempt(missed, 0.0)["axes"]["verification"] == 0.0   # 8/20*20 - 10, clamped


  def test_text_only_ciel_use_makes_verification_na_but_scores_prompting():
      events = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "what is the expected output format?"}),
                _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": []})]
      res = score_attempt(events, 0.0)
      assert res["axes"]["prompting"] is not None
      assert res["axes"]["verification"] is None
  ```

**Step 2: Run to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_scoring_engine.py -q`
Expected: FAIL (e.g. `KeyError: 'not_applicable'`, `TypeError: unexpected keyword argument 'exercise_kind'`)

**Step 3: Replace `app/features/scoring/engine.py`** with:

```python
from app.features.scoring.features import AxisFeatures, compute_features

WEIGHTS = {"understanding": 0.25, "hypothesis": 0.22, "prompting": 0.18,
           "verification": 0.15, "testing": 0.10, "debugging": 0.10}

# Why an axis is "not applicable" (None): the session gave no opportunity to
# observe that skill, which is not the same as the student being weak at it.
# N/A axes are excluded from `overall` (the remaining weights renormalise).
NA_REASONS = {
    "prompting": "no_ai_use",
    "verification": "no_ai_code",
    "debugging": "no_failure",
}


def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))


# ── Scoring philosophy (rev. 2026-09-24, P0) ─────────────────────────────────
# Every axis is earned from evidence. An axis the session had no opportunity to
# show is N/A rather than 0. The constants below are interim: phase P1 replaces
# them with evidence-centred rubrics (docs/superpowers/specs/2026-09-24-scoring-roadmap.md).

def _understanding(f: AxisFeatures) -> float:
    # Driven almost entirely by the explain-back score (0-20, LLM-judged). The
    # small engagement bonus is tied to actually SOLVING (a fully-passing run),
    # not to typing characters - so gibberish like "asfasdf" earns nothing.
    # Shallow concept-only prompts and a rushed start reduce it.
    u1 = -3 if (f.first_prompt_delay_ms is not None and f.first_prompt_delay_ms < 20000
                and f.problem_read_ratio < 0.6) else 0
    engage = 2 if f.any_pass else 0
    return clamp(0, 20, 0.9 * f.explain_score + engage - 2 * f.u2_hits + u1)


def _hypothesis(f: AxisFeatures) -> float:
    # No hypothesis logged => 0 (the hypothesis box is always available).
    # Correctness dominates; AI-proposed hypotheses subtract.
    if f.hypothesis_count == 0:
        return 0.0
    raw = 3 + 9 * f.h1_count + (5 if f.has_hypothesis_before_code else 0) - 4 * f.h2_count
    return clamp(0, 20, raw)


def _prompting(f: AxisFeatures) -> float | None:
    if f.prompt_count == 0:
        return None
    cap = 12 if f.p1_ratio > 0.3 else 20
    raw = 10 + 3 * f.p3_hits - 2 * f.p1_hits - 3 * f.p2_clusters - 1 * f.p4_hits
    return clamp(0, cap, raw)


def _verification(f: AxisFeatures) -> float | None:
    # Verifying AI output needs AI output: with no code-bearing reply and no
    # planted trap there is nothing to verify, so the axis is N/A.
    if not (f.ai_code_received or f.trap_injected):
        return None
    earned = (12 if f.has_v1 else 0) + (8 if f.tested_after_ai_code else 0)
    possible = 8 + (12 if f.trap_injected else 0)
    penalty = (10 if f.has_v1b else 0) + 4 * f.v2_count + (6 if f.has_v3 else 0)
    return clamp(0, 20, 20 * earned / possible - penalty)


def _testing(f: AxisFeatures) -> float:
    # Interim until students write their own tests (P2): how much of the suite
    # the final run passed. Independent of how many cases the author wrote.
    if f.run_count == 0:
        return 0.0
    return clamp(0, 20, 20 * f.final_pass_ratio)


def _debugging(f: AxisFeatures, exercise_kind: str) -> float | None:
    # Debug-kind exercises start broken, so there is always something to debug.
    # On implement exercises only a real failing run of the student's own code
    # creates that opportunity; a first-try pass is N/A, not a weakness.
    fails = f.real_fails_before_first_pass
    is_debug = exercise_kind == "debug"
    if not is_debug and fails == 0:
        return None
    if not f.any_pass:
        return 0.0
    if is_debug:
        return clamp(12, 20, 20 - 2 * fails)
    # Tops out at 16 so needing fixes never beats an otherwise equal clean solve.
    return clamp(10, 16, 16 - 2 * (fails - 1))


def integrity_multiplier(f: AxisFeatures) -> float:
    """Scale every axis down when the session shows cheating signals.

    Pasting an answer from another AI is the exact abuse this platform exists to
    catch, so each paste (blocked or burst) is weighted heavily; leaving the tab
    to copy from elsewhere (FOCUS_LOST) is a softer signal. With no flags the
    multiplier is 1.0, so honest attempts are unaffected.
    """
    penalty = 0.12 * f.paste_flags + 0.06 * f.focus_lost
    return clamp(0.4, 1.0, 1.0 - penalty)


def score_attempt(events: list[dict], explain_score: float | None, exercise_kind: str = "implement") -> dict:
    f = compute_features(events, explain_score)
    mult = integrity_multiplier(f)
    raw: dict[str, float | None] = {
        "understanding": _understanding(f),
        "hypothesis": _hypothesis(f),
        "prompting": _prompting(f),
        "verification": _verification(f),
        "testing": _testing(f),
        "debugging": _debugging(f, exercise_kind),
    }
    # The integrity multiplier applies to every scored axis so a compromised
    # session cannot report "Strong understanding" off a pasted explanation.
    axes = {a: (round(v * mult, 2) if v is not None else None) for a, v in raw.items()}
    active = {a: v for a, v in axes.items() if v is not None}
    total_weight = sum(WEIGHTS[a] for a in active)
    overall = round(5 * sum((WEIGHTS[a] / total_weight) * v for a, v in active.items()), 2) if total_weight else 0.0
    return {
        "axes": axes,
        "overall": clamp(0, 100, overall),
        "features": f,
        "integrity_multiplier": mult,
        "not_applicable": {a: NA_REASONS[a] for a, v in axes.items() if v is None},
    }
```

**Step 4: Run to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_scoring_engine.py tests/test_features.py -q`
Expected: all PASS

**Step 5: Commit**

```bash
git add app/features/scoring/engine.py tests/test_scoring_engine.py
git commit -m "fix(scoring): mark axes without opportunity N/A and stop debugging farming"
```

---

### Task 6: Delete the unused YAML rules

`app/rules/*.yaml` are loaded but never used, and their numbers already disagree with the engine. Task 5 removed the only caller (`load_rules()` in `score_attempt`).

**Files:**
- Delete: `app/rules/` (all six YAML files), `app/features/scoring/rules_loader.py`, `tests/test_rules_loader.py`

**Step 1: Confirm nothing else references them**

Run: `grep -rn "rules_loader\|load_rules\|app/rules" app tests alembic Dockerfile`
Expected: no output

**Step 2: Delete**

```bash
git rm -r app/rules app/features/scoring/rules_loader.py tests/test_rules_loader.py
```

**Step 3: Run the full suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: failures only in `tests/test_mentor.py`, `tests/test_submit_flow.py` or `tests/test_dashboard.py` if any (fixed in Tasks 7–9). No import errors.

**Step 4: Commit**

```bash
git commit -m "chore(scoring): remove unused YAML rule files"
```

---

### Task 7: Nullable Prompting/Verification columns + report feedback carries N/A reasons

**Files:**
- Modify: `app/models/fluency_report.py`
- Create: `alembic/versions/f2c4d6e8a1b3_nullable_prompt_verification_scores.py`
- Modify: `app/features/attempts/scoring_service.py`
- Test: `tests/test_submit_flow.py`

**Step 1: Write the failing test** (append to `tests/test_submit_flow.py`; the seeded attempt has no prompt and no run)

```python
async def test_report_marks_axes_without_opportunity_not_applicable(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    eb = await client.post(
        f"/api/attempts/{aid}/explain-back", headers=auth_headers,
        json={"answers": [{"question": "q", "answer": "Because I use a hash map for O(1) lookups."}]},
    )
    body = eb.json()
    assert body["axes"]["prompting"] is None
    assert body["axes"]["verification"] is None
    assert body["axes"]["debugging"] is None
    assert body["feedback"]["not_applicable"] == {
        "prompting": "no_ai_use", "verification": "no_ai_code", "debugging": "no_failure",
    }
    rep = (await client.get(f"/api/attempts/{aid}/report", headers=auth_headers)).json()
    assert rep["axes"]["prompting"] is None
    assert rep["feedback"]["not_applicable"] == body["feedback"]["not_applicable"]
```

**Step 2: Run to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_submit_flow.py -q`
Expected: FAIL (`IntegrityError: NOT NULL constraint failed: fluency_reports.prompt_score`)

**Step 3: Implement**

a) `app/models/fluency_report.py`:

```python
    prompt_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
```

b) `alembic/versions/f2c4d6e8a1b3_nullable_prompt_verification_scores.py`:

```python
"""prompt/verification scores nullable (axis may be not applicable)

Revision ID: f2c4d6e8a1b3
Revises: a7d24c8e9b31
Create Date: 2026-09-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f2c4d6e8a1b3"
down_revision: Union[str, None] = "a7d24c8e9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("fluency_reports", "prompt_score", existing_type=sa.Float(), nullable=True)
    op.alter_column("fluency_reports", "verification_score", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    # N/A cannot be represented once the columns are NOT NULL again: store 0.
    op.execute("UPDATE fluency_reports SET prompt_score = 0 WHERE prompt_score IS NULL")
    op.execute("UPDATE fluency_reports SET verification_score = 0 WHERE verification_score IS NULL")
    op.alter_column("fluency_reports", "prompt_score", existing_type=sa.Float(), nullable=False)
    op.alter_column("fluency_reports", "verification_score", existing_type=sa.Float(), nullable=False)
```

c) `app/features/attempts/scoring_service.py`:

- `build_feedback` gets a third parameter and returns the reasons:

  ```python
  def build_feedback(axes: dict, f: AxisFeatures, not_applicable: dict[str, str] | None = None) -> dict:
      ...  # body unchanged
      return {"strengths": strengths[:4], "risks": risks[:4], "per_axis": per_axis,
              "not_applicable": dict(not_applicable or {})}
  ```

- Add, below `build_timeline`, the single place that maps an engine result onto report columns (used by explain-back now and by rescoring in Task 10):

  ```python
  def report_columns(result: dict) -> dict:
      """FluencyReport column values for a score_attempt() result."""
      axes, f = result["axes"], result["features"]
      return {
          "understanding_score": axes["understanding"],
          "hypothesis_score": axes["hypothesis"],
          "prompt_score": axes["prompting"],
          "verification_score": axes["verification"],
          "testing_score": axes["testing"],
          "debugging_score": axes["debugging"],
          "overall_score": result["overall"],
          "feedback": {**build_feedback(axes, f, result["not_applicable"]), "timeline": build_timeline(f)},
      }
  ```

- In `score_with_explanations`, replace everything from `events = await _events_as_dicts(...)` down to the `return` with:

  ```python
      ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
      events = await _events_as_dicts(db, attempt.id)
      result = score_attempt(events, explain_score=explain_score, exercise_kind=ex.kind)
      f = result["features"]
      integrity = integrity_from_features(f)

      db.add(FluencyReport(attempt_id=attempt.id, explanation_score=explain_score, **report_columns(result)))
      attempt.score = result["overall"]
      attempt.status = "scored"
      attempt.integrity_status = integrity
      await db.commit()

      return _report_payload(result["axes"], result["overall"], f, integrity, result["not_applicable"])
  ```

- `_report_payload` takes `not_applicable: dict[str, str]` as a fifth parameter and uses `build_feedback(axes, f, not_applicable)`.

`GET /report` already returns the stored `feedback` (minus `timeline`), so `not_applicable` flows through with no router change. Old reports simply lack the key until rescored.

**Step 4: Run to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_submit_flow.py tests/test_scoring_engine.py -q`
Expected: PASS

**Step 5: Check the migration against real Postgres** (Docker Desktop must be running)

```bash
docker run -d --name cp_mig_db -e POSTGRES_PASSWORD=x -p 127.0.0.1:55432:5432 postgres:16
```

Wait ~5 s, then (bash):

```bash
DATABASE_URL=postgresql+asyncpg://postgres:x@localhost:55432/postgres ../../../.venv/Scripts/python.exe -m alembic upgrade head && DATABASE_URL=postgresql+asyncpg://postgres:x@localhost:55432/postgres ../../../.venv/Scripts/python.exe -m alembic downgrade -1 && DATABASE_URL=postgresql+asyncpg://postgres:x@localhost:55432/postgres ../../../.venv/Scripts/python.exe -m alembic upgrade head
```

Expected: three runs with no error, ending at `f2c4d6e8a1b3`. Then clean up: `docker rm -f cp_mig_db`.

**Step 6: Commit**

```bash
git add app/models/fluency_report.py alembic/versions/f2c4d6e8a1b3_nullable_prompt_verification_scores.py app/features/attempts/scoring_service.py tests/test_submit_flow.py
git commit -m "feat(reports): store N/A axes as null and expose their reasons in feedback"
```

---

### Task 8: Stop exposing the injected-bug flag to the client

The `/mentor` response returned `injected_error`, which the UI used to label exactly the trapped reply, and anyone could read it in devtools. The event log keeps the flag for scoring.

**Files:**
- Modify: `app/schemas/mentor.py`, `app/features/mentor/service.py`
- Test: `tests/test_mentor.py`

**Step 1: Update the tests.** In `test_mentor_injects_error_once`, replace the two `injected_error` response assertions with checks on the event log, and assert the key is gone:

```python
    assert "injected_error" not in r1.json()
    ...
    ai_events = [e for e in await _events(db_session, aid) if e.type == "AI_REPLY"]
    assert [e.payload["injectedError"] for e in ai_events] == [True, False]  # only once per attempt
```

(keep the existing PROMPT keyword assertion). In `test_no_trap_no_injection` replace the assertion with:

```python
    ai_ev = next(e for e in await _events(db_session, aid) if e.type == "AI_REPLY")
    assert ai_ev.payload["injectedError"] is False
```

**Step 2: Run to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_mentor.py -q`
Expected: FAIL on `assert "injected_error" not in r1.json()`

**Step 3: Implement.** In `app/schemas/mentor.py` delete the `injected_error: bool` field from `MentorOut`. In `app/features/mentor/service.py` change the return of `mentor_reply` to `return {"reply": result["text"]}`.

**Step 4: Run to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_mentor.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add app/schemas/mentor.py app/features/mentor/service.py tests/test_mentor.py
git commit -m "fix(mentor): stop revealing which reply carries the injected bug"
```

---

### Task 9: Dashboard radar returns null for never-observed axes

**Files:**
- Modify: `app/schemas/dashboard.py`, `app/features/dashboard/service.py`
- Test: `tests/test_dashboard.py`

**Step 1: Write the failing test** (append to `tests/test_dashboard.py`)

```python
async def test_radar_axis_is_null_when_never_observed(client, db_session, auth_headers):
    from app.models import Attempt, Exercise, FluencyReport, User
    from sqlalchemy import select
    user = (await db_session.execute(select(User))).scalars().first()
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", acceptance=1, summary="s", starter_code="x",
                  hint="h", domain_keywords=["a"])
    db_session.add(ex); await db_session.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, score=90.0, status="scored", integrity_status="green")
    db_session.add(at); await db_session.flush()
    db_session.add(FluencyReport(attempt_id=at.id, understanding_score=18, hypothesis_score=17,
                                 prompt_score=None, verification_score=None, testing_score=20,
                                 debugging_score=None, explanation_score=18, overall_score=90.0, feedback={}))
    await db_session.commit()

    radar = {r["name"]: r["value"] for r in (await client.get("/api/dashboard", headers=auth_headers)).json()["radar"]}
    assert radar["Prompting"] is None
    assert radar["Debugging"] is None
    assert radar["Testing"] == 100.0
```

**Step 2: Run to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_dashboard.py -q`
Expected: FAIL (`assert 0.0 is None`)

**Step 3: Implement.** `app/schemas/dashboard.py`: `value: float | None  # 0..100; None = never observed`. `app/features/dashboard/service.py`, in the radar loop:

```python
        radar.append({"name": name, "value": round((sum(vals) / len(vals)) * 5, 1) if vals else None})
```

**Step 4: Run the full backend suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS

**Step 5: Commit**

```bash
git add app/schemas/dashboard.py app/features/dashboard/service.py tests/test_dashboard.py
git commit -m "fix(dashboard): report never-observed radar axes as null instead of 0"
```

---

### Task 10: Rescore existing reports

**Files:**
- Create: `app/features/scoring/rescore.py`
- Create: `tests/test_rescore.py`
- Modify: `docs/RUNBOOK.md` (Production section)

**Step 1: Write the failing test** (`tests/test_rescore.py`)

```python
import pytest
from sqlalchemy import select

from app.features.scoring.rescore import rescore_all

pytestmark = pytest.mark.asyncio


async def _legacy_report(db_session):
    """A first-try solve scored by the old engine (debugging 0, no prompt)."""
    from app.models import Attempt, Event, Exercise, FluencyReport, User

    user = User(full_name="U", email="u@example.com", password_hash="x")
    ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher",
                  language="python", summary="s", starter_code="x", hint="h", domain_keywords=[])
    db_session.add_all([user, ex]); await db_session.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, score=53.45, status="scored", integrity_status="green")
    db_session.add(at); await db_session.flush()
    for t, ts, p in [("OPEN", 0, {"problemReadRatio": 1.0}),
                     ("HYPOTHESIS", 30000, {"proposedBy": "user", "correct": True}),
                     ("CODE_EDIT", 60000, {"charsAdded": 200}),
                     ("RUN", 90000, {"passed": True}),
                     ("SUBMIT", 95000, {})]:
        db_session.add(Event(attempt_id=at.id, type=t, ts=ts, payload=p, integrity_flags=[]))
    db_session.add(FluencyReport(attempt_id=at.id, understanding_score=18.2, hypothesis_score=17,
                                 prompt_score=0, verification_score=8, testing_score=12,
                                 debugging_score=0, explanation_score=18, overall_score=53.45, feedback={}))
    await db_session.commit()
    return at.id


async def test_dry_run_reports_changes_without_writing(db_session):
    from app.models import FluencyReport

    aid = await _legacy_report(db_session)
    changes = await rescore_all(db_session, apply=False)
    assert len(changes) == 1
    assert changes[0]["attempt_id"] == aid
    assert changes[0]["old"] == 53.45
    assert changes[0]["new"] > 85
    rep = (await db_session.execute(select(FluencyReport))).scalar_one()
    assert rep.overall_score == 53.45        # untouched


async def test_apply_rewrites_report_and_attempt(db_session):
    from app.models import Attempt, FluencyReport

    await _legacy_report(db_session)
    changes = await rescore_all(db_session, apply=True)
    rep = (await db_session.execute(select(FluencyReport))).scalar_one()
    at = (await db_session.execute(select(Attempt))).scalar_one()
    assert rep.overall_score == changes[0]["new"]
    assert at.score == changes[0]["new"]
    assert rep.debugging_score is None
    assert rep.prompt_score is None
    assert rep.explanation_score == 18            # the LLM judgement is reused, not re-asked
    assert rep.feedback["rescored_from"]["overall"] == 53.45
    assert rep.feedback["not_applicable"]["debugging"] == "no_failure"
    assert len(rep.feedback["timeline"]) == 3
```

**Step 2: Run to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_rescore.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.features.scoring.rescore'`

**Step 3: Implement `app/features/scoring/rescore.py`**

```python
"""Recompute stored fluency reports with the current scoring engine.

    python -m app.features.scoring.rescore          # dry run: print old -> new
    python -m app.features.scoring.rescore --apply  # write the new scores

Scores are rebuilt from each attempt's stored events and its stored
explain-back score (the LLM is not called again). Each rewritten report keeps
its previous overall under feedback["rescored_from"].
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.attempts.scoring_service import _events_as_dicts, integrity_from_features, report_columns
from app.features.scoring.engine import score_attempt
from app.models import Attempt, Exercise, FluencyReport


async def rescore_all(db: AsyncSession, apply: bool) -> list[dict]:
    rows = (await db.execute(
        select(FluencyReport, Attempt, Exercise)
        .join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .join(Exercise, Exercise.id == Attempt.exercise_id)
        .order_by(FluencyReport.id)
    )).all()
    changes: list[dict] = []
    for report, attempt, exercise in rows:
        events = await _events_as_dicts(db, attempt.id)
        result = score_attempt(events, explain_score=report.explanation_score, exercise_kind=exercise.kind)
        changes.append({"attempt_id": attempt.id, "exercise": exercise.code,
                        "old": report.overall_score, "new": result["overall"]})
        if not apply:
            continue
        previous = report.overall_score
        for column, value in report_columns(result).items():
            setattr(report, column, value)
        report.feedback = {**report.feedback, "rescored_from": {
            "overall": previous, "at": datetime.now(timezone.utc).isoformat()}}
        attempt.score = result["overall"]
        attempt.integrity_status = integrity_from_features(result["features"])
    if apply:
        await db.commit()
    return changes


async def _main(apply: bool) -> None:
    async with async_session_maker() as db:
        changes = await rescore_all(db, apply)
    for c in changes:
        print(f"attempt {c['attempt_id']:>6}  {c['exercise']:<8}  {c['old']:6.2f} -> {c['new']:6.2f}")
    verb = "rescored" if apply else "would rescore (dry run, use --apply to write)"
    print(f"{len(changes)} report(s) {verb}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the new scores (default: dry run)")
    asyncio.run(_main(parser.parse_args().apply))
```

Note: `report_columns` builds `feedback` without `rescored_from`, so the code above re-adds it after the column loop. Move `_events_as_dicts` to a public name only if a reviewer asks; importing the private helper keeps this change small.

**Step 4: Run to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_rescore.py -q`
Expected: PASS

**Step 5: Document in `docs/RUNBOOK.md`** (append to the Production section)

````markdown
## Rescoring reports after a scoring change

Take a backup first (`scripts/backup_db.sh`, or at least
`docker exec codeprove_db pg_dump -U codeprove -d codeprove -Fc > ~/pre_rescore.dump`),
deploy the new code, then:

```bash
docker exec codeprove_backend python -m app.features.scoring.rescore          # dry run
docker exec codeprove_backend python -m app.features.scoring.rescore --apply  # write
```

Scores are rebuilt from stored events and the stored explain-back score; the LLM
is not called. Each report keeps its previous overall in `feedback.rescored_from`.
````

**Step 6: Run the full suite and commit**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS

```bash
git add app/features/scoring/rescore.py tests/test_rescore.py docs/RUNBOOK.md
git commit -m "feat(scoring): add rescore command for existing reports"
```

---

### Task 11: Frontend — set up the branch

**Step 1:** From `D:/FPT_University/Ki_7/EXE101/Product/codeprove-web`:

```bash
git fetch origin && git worktree add .claude/worktrees/p0-scoring-na -b feat/p0-scoring-na origin/main
```

**Step 2:** In the new worktree: `npm ci`, then `npm test` and `npm run build`. Record the baseline (both must pass before changes).

All frontend paths below are relative to that worktree.

---

### Task 12: Frontend — generic "AI can be wrong" hint on every code reply

**Files:**
- Create: `lib/chat.ts`
- Modify: `components/workspace/PromptLog.tsx`, `components/app/SolveWorkspace.tsx:652`, `lib/types/session.ts`, `lib/types/ciel.ts`, `lib/api/ciel.ts` (doc comment), `lib/appContent.ts` (`verifyHint` vi/en)
- Test: `tests/ui.test.cjs`

**Step 1: Write the failing test** (append to `tests/ui.test.cjs`)

```js
const { hasCodeBlock } = require('../lib/chat.ts');

test('hasCodeBlock detects fenced code only', () => {
  assert.equal(hasCodeBlock('Try this:\n```python\nx = 1\n```'), true);
  assert.equal(hasCodeBlock('Think about the loop bounds.'), false);
  assert.equal(hasCodeBlock('Use `range(n)` inline'), false);
});
```

**Step 2: Run to verify it fails**

Run: `npm test`
Expected: FAIL (`Cannot find module '../lib/chat.ts'`)

**Step 3: Implement**

`lib/chat.ts`:

```ts
/** True when a chat reply contains a fenced code block (```...```). */
export const hasCodeBlock = (text: string): boolean => /```[\s\S]*?```/.test(text);
```

`components/workspace/PromptLog.tsx`: import `hasCodeBlock` from `@/lib/chat`, update the `verifyHint` label doc comment to "Footnote under every reply that contains code (AI code can be wrong).", and replace the `{m.verifyHint && (...)}` block with:

```tsx
          {m.role === "assistant" && hasCodeBlock(m.text) && (
            <p className="mt-1 text-xs italic text-on-surface-variant/60">{labels.verifyHint}</p>
          )}
```

`components/app/SolveWorkspace.tsx:652`: `addPromptEntry({ role: "assistant", text: res.reply });`

`lib/types/session.ts`: delete the `verifyHint?: boolean;` field and its doc line. `lib/types/ciel.ts`: delete `injected_error: boolean;` and fix the doc comment. `lib/api/ciel.ts`: doc comment says the response is `{ reply }`.

`lib/appContent.ts`: `verifyHint` → vi `"AI có thể sai — hãy chạy thử và kiểm chứng trước khi dùng."`, en `"AI can be wrong — run and verify it before you use it."`

**Step 4: Verify**

Run: `npm test && npm run build`
Expected: PASS; build has no type errors (a leftover `verifyHint`/`injected_error` reference would fail here).

**Step 5: Commit**

```bash
git add lib/chat.ts components/workspace/PromptLog.tsx components/app/SolveWorkspace.tsx lib/types/session.ts lib/types/ciel.ts lib/api/ciel.ts lib/appContent.ts tests/ui.test.cjs
git commit -m "fix(ciel): show the verify reminder on every code reply, not just the trap"
```

---

### Task 13: Frontend — show N/A axes with their reason

**Files:**
- Modify: `lib/types/report.ts`, `lib/types/dashboard.ts`, `components/report/RadarChart.tsx`, `app/(app)/feedback/FeedbackContent.tsx`, `app/(app)/dashboard/page.tsx`, `components/app/WorkspaceLanding.tsx`, `lib/appContent.ts`
- Test: `tests/ui.test.cjs`

**Step 1: Write the failing test** (append to `tests/ui.test.cjs`)

```js
const { RadarChart } = require('../components/report/RadarChart.tsx');

test('RadarChart marks not-applicable axes instead of plotting them as a score', () => {
  const html = render(h(RadarChart, { data: [
    { label: 'Understanding', value: 90 },
    { label: 'Hypothesis', value: 85 },
    { label: 'Debugging', value: null },
  ] }));
  assert.match(html, /Debugging —/);
  assert.doesNotMatch(html, /Understanding —/);
});
```

**Step 2: Run to verify it fails**

Run: `npm test`
Expected: FAIL (no `Debugging —` in the markup)

**Step 3: Implement**

- `lib/types/report.ts`: add to `feedback`: `not_applicable?: Record<string, "no_failure" | "no_ai_use" | "no_ai_code">;`
- `lib/types/dashboard.ts`: `radar: { name: string; value: number | null }[];`
- `components/report/RadarChart.tsx` label `<text>`: add `opacity={d.value === null ? 0.45 : 1}` and render `{d.value === null ? `${d.label} —` : d.label}`. Update the header comment: "null = not applicable (drawn at the centre, label dimmed)".
- `lib/appContent.ts`, in both `feedback` blocks, add:
  - vi: `naLabel: "Không áp dụng"`, `naReasons: { no_failure: "Code của bạn không phát sinh lỗi nên không có gì để debug.", no_ai_use: "Bạn không dùng Ciel trong lượt này.", no_ai_code: "Ciel không đưa code nào để bạn kiểm chứng." }`
  - en: `naLabel: "Not applicable"`, `naReasons: { no_failure: "Your code never failed, so there was nothing to debug.", no_ai_use: "You didn't use Ciel in this attempt.", no_ai_code: "Ciel gave you no code to verify." }`
- `app/(app)/feedback/FeedbackContent.tsx`, axis bars: when `isNull`, show `tf.naLabel` instead of `-` on the right, and under the dimmed bar add
  ```tsx
  {isNull && report.feedback.not_applicable?.[key] && (
    <p className="mt-1 text-xs text-on-surface-variant/60">{tf.naReasons[report.feedback.not_applicable[key]]}</p>
  )}
  ```
- `app/(app)/dashboard/page.tsx`: `computeRadarPoints(values: (number | null)[])` with `const r = (Math.min(Math.max(v ?? 0, 0), 100) / 100) * maxR;`; in the labels map, look up the axis value (`const v = data?.radar.find((r) => r.name === l.name)?.value;`) and dim + suffix `—` when `v === null`, same as the RadarChart.
- `components/app/WorkspaceLanding.tsx`: pick the weakest axis only among observed ones:
  ```tsx
  const radar = (dashQuery.data?.radar ?? []).filter((r): r is { name: string; value: number } => r.value !== null);
  ```

**Step 4: Verify**

Run: `npm test && npm run build`
Expected: PASS

**Step 5: Manual check** (`npm run dev` against a backend running this branch): a first-try solve without Ciel shows Prompting / Verification / Debugging as "Không áp dụng" with their reason on the Feedback page, dimmed on both radars, and the Workspace "weakest axis" tip ignores them.

**Step 6: Commit**

```bash
git add lib/types/report.ts lib/types/dashboard.ts components/report/RadarChart.tsx "app/(app)/feedback/FeedbackContent.tsx" "app/(app)/dashboard/page.tsx" components/app/WorkspaceLanding.tsx lib/appContent.ts tests/ui.test.cjs
git commit -m "feat(feedback): show not-applicable axes with their reason"
```

---

### Task 14: Wrap-up

1. Backend: `../../../.venv/Scripts/python.exe -m pytest -q` → all pass; re-run the persona simulation (first-try solve > needs-fixes > farming does not help) and paste the numbers in the PR.
2. Push both branches; open PRs (backend first, it is backward compatible: old frontend simply stops showing the trap label because `injected_error` is gone).
3. Deploy order on EC2: backup → pull backend → `docker compose up -d --build` (runs the migration) → rescore dry run → `--apply` → deploy frontend.
