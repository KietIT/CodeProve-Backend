# P1.2 Hidden Tests at Submit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When a student submits, run the exercise's full test suite (visible + hidden) on the submitted code, score the Testing axis from it, tell the student only the counts and failing categories right away, and keep the failing inputs for the Feedback page.

**Architecture:** `/submit` runs the suite synchronously in the existing sandbox on the latest snapshot (the frontend force-saves one right before submitting) and logs a `SUBMIT_TESTS` event. Scoring features read the last such event; the report feedback carries a `submit_tests` section with the failures. Backend only; the UI is P1.6.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest (real subprocess sandbox in tests).

**Design:** `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.2). Decision taken: synchronous at submit (adds the suite's run time, a few seconds at most, to submit).

---

## Roadmap traceability

| Item | Task |
|---|---|
| [2] Hidden-test display policy: categories on submit, full input on Feedback (backend half) | 2, 4 |
| P1.2 design: run the full suite at submit, log `SUBMIT_TESTS` | 1, 2 |
| P1.2 design: Testing axis from the submit suite | 3 |

## API contract (for the P1.6 frontend plan)

- `POST /api/attempts/{id}/submit` → `{"questions": [...], "tests": null | {"passed", "total", "hidden_passed", "hidden_total", "failed_categories": [...]}}`. Never inputs.
- Report (`explain-back` response and `GET /report`): `feedback.submit_tests` = `null | {"passed", "total", "hidden_passed", "hidden_total", "failed_categories", "failures": [{"description", "category", "hidden", "input", "expected", "actual", "error"}]}`. Strings clipped to 300 chars.
- Timeline `implementation` item: `coverage_pct` = pass % of the suite at submit when available.
- Submitting a scored attempt returns 409.

---

### Task 1: The sandbox reports the actual value of each case

`app/features/sandbox/runner.py`: in `_HARNESS` add `"actual": None` to each case's `out` dict and set `out["actual"] = got[:500]` right after `got = repr(value)`; in `_result`'s fallback cases add `"actual": None`. `RunCase` ignores the extra key, so `/run` is unchanged.

Test (`tests/test_sandbox.py`): a case `f()` expecting `"42"` against `def f(): return 41` reports `actual == "41"` and `passed is False`.

Commit: `feat(sandbox): report each case's actual value`

### Task 2: Run the suite at submit

Create `app/features/attempts/submit_tests.py` with `run_submit_suite(db, attempt) -> dict | None` (all test cases ordered by `order_index`, latest snapshot or `""`, sandbox run, `SUBMIT_TESTS` event whose payload holds `passRatio, passed, total, visiblePassed, visibleTotal, hiddenPassed, hiddenTotal, failedCategories` (hidden only, sorted, `None` → `"uncategorized"`), `failures` (clipped `description, category, hidden, input, expected, actual, error`); `None` when the exercise has no tests) and `public_summary(payload)` (counts + categories only).

`router.submit`: 409 if the attempt is already scored; apply the sandbox rate limit; run the suite before logging `SUBMIT`; return `{"questions", "tests": public_summary(...)}`.

Tests (`tests/test_submit_tests.py`, real sandbox, LLM faked as in `test_submit_flow.py`): 1 visible + 2 hidden (boundary, edge) exercise; snapshot passing the visible and the boundary test → response `tests == {passed 2, total 3, hidden_passed 1, hidden_total 2, failed_categories ["edge"]}` and no inputs anywhere in the response; the `SUBMIT_TESTS` event's failure carries input/expected/actual. No snapshot → `passed 0`. Resubmitting a scored attempt → 409.

Commit: `feat(attempts): run the full test suite at submit`

### Task 3: Testing axis from the submit suite

`features.py`: `submit_tests: dict | None` = payload of the last `SUBMIT_TESTS` event; a full pass there also sets `any_pass`. `engine._testing`: `20 × passRatio` of the submit suite when present, else the P0 fallback (last run).

Tests: suite at submit wins over runs; a full pass at submit without any run sets `any_pass`.

Commit: `feat(scoring): score Testing from the full suite at submit`

### Task 4: Report carries the failures

`scoring_service.build_feedback` adds `submit_tests` (counts, categories, failures) from the features; `build_timeline`'s `implementation` item uses the submit pass % when available.

Test: after submit + explain-back, the report's `feedback.submit_tests.failures[0]` has the hidden input, and `axes.testing == round(20 * 2 / 3, 2)`.

Commit: `feat(reports): include submit test failures in the feedback`

### Task 5: Wrap-up

Full suite green; push; PR. Deploy: `git pull && docker compose up -d --build` (no migration). Old reports are unaffected (no `SUBMIT_TESTS` events; Testing falls back).
