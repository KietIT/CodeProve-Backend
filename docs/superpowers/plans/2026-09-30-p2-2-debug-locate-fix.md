# P2.2 Debug Exercise Mode: Locate → Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** On the 9 debug exercises the student first **locates** the bug (clicks the buggy line(s) in the read-only starter and says why, with optional hints), then **fixes** it in the editor. The Debugging axis of these exercises is scored from four indicators (located, explained, fixed, efficiency), and after submit the Feedback page reveals where the bug was and why.

**Architecture:** Per-exercise debug metadata (bug regions, explanation, one authored hint) lives in the reviewed content files and is synced into a new `exercises.debug_meta` JSON column. Two endpoints record `DEBUG_HINT` and `LOCATE` events (no correctness feedback before submit). An anchored LLM judge rates the locate reason at explain-back, like the other judges (`JUDGE` event, kind `locate`). `rubric.debugging` uses the new indicators only when a `LOCATE` event exists, so old sessions keep their scores without an engine switch (design decision 6). New finding codes + templates feed the Feedback page; the frontend work goes to the CodeProve-UI session.

**Tech Stack:** FastAPI, SQLAlchemy async + Alembic, pydantic v2, pytest; `MentorClient.judge` (JSON, temperature 0); `difflib`; the P0 `strip_comments` serve-time starter.

**Design:** `docs/superpowers/specs/2026-09-29-p2-design.md` (P2.2, decisions of 2026-09-30); roadmap "Debug exercise mode".

---

## Facts this plan relies on (checked 2026-09-30)

- The student sees `strip_comments(starter)` (P0: comments leak the bug; comment-only lines are dropped, so line numbers are those of the stripped code). Regions must use the same numbering.
- Diffing the served starter against the reference (`difflib`, replace/delete ops) gives the right region for 7/9 exercises:

| Exercise | Served lines | Derived regions | Proposed region(s) |
|---|---|---|---|
| CP-004 off-by-one | 5 | [3] | [3] |
| CP-008 null reference | 2 | [2] | [2] |
| CP-012 race condition | 5 | inserts before 1, 2 + [5] | **[5]** (the inserts add a lock; no line to click) |
| CP-102 unbounded cache | 6 | [1], [4, 5] | **[1, 4, 5]** (one bug: nothing evicts) |
| CP-106 SQL injection | 4 | [3] | [3] |
| CP-109 lost cause | 5 | [4, 5] | [4, 5] |
| CP-203 auth bypass | 13 | [11] | [11] |
| CP-206 deadlock | 5 | [2, 3] | [2, 3] |
| CP-208 upload | 10 | [7], [9] | [7] path traversal, [9] unchecked type/size |

- `exercises.buggy_location` exists but was never used; a JSON column is added instead of reusing a text column with another meaning.

## Rules (decided in this plan unless Kiệt says otherwise)

- **Locate first:** on a debug exercise the editor stays read-only until the student submits a location or skips. The backend records it; it does not block runs (the UI does), so an old client cannot break.
- **No correctness feedback before submit:** a location is recorded, not graded live, so it cannot be brute-forced; the answer is revealed on the Feedback page.
- **Selection:** at least 1 and at most `regions + 1` lines, plus a reason (≤ 500 chars, may be empty only when skipping).
- **Hints:** 2 steps, bought before locating: (1) the authored hint (kind of bug, e.g. "a loop boundary"), (2) a line range: the regions widened by 1 line each side. No hint gives the exact line.
- **Levels:**

| Indicator | 3 | 2 | 1 | 0 |
|---|---|---|---|---|
| Located | every region hit, no hint | every region hit with 1 hint, or some regions hit with none | every region hit with 2 hints, or some hit with hints | no region hit / skipped |
| Explained (LLM, vs the authored explanation) | names the cause and why it breaks | names the cause, vague on why | vague | wrong / empty / skipped |
| Fixed | full suite passes | visible pass, hidden fail | at least one visible test passes | no visible test passes |
| Efficiency (only when fixed) | 0–1 failing runs | 2–3 | ≥ 4 | — |

  Axis level = rounded mean of the applicable indicators (P1.4 convention). Without a `LOCATE` event (old sessions, old clients) the P1.4 indicator applies unchanged.

---

### Task 1: Debug metadata in content files

**Files:** Modify `app/features/content/schema.py`, `app/features/content/validate.py`; create `app/features/exercises/debug_regions.py`; modify the 9 files `content/exercises/CP-{004,008,012,102,106,109,203,206,208}.json`; tests `tests/test_debug_regions.py`, `tests/test_content_validate.py`.

- `debug_regions.derive(served_starter, reference) -> list[list[int]]`: 1-based lines of replace/delete ops on the served (comment-stripped) starter; pure inserts attach to no region unless the diff has nothing else (then the line after the insertion).
- Schema: optional `debug` block: `regions` (optional override, list of line lists), `explanation_vi`, `explanation_en` (≤ 400 chars), `hint_vi`, `hint_en` (≤ 120 chars, must not quote a line of the starter), and its own `review` (status/author/reviewer, the P1.1 convention) so adding it does not un-approve the rest of the file.
- Validator: `debug` required when the exercise kind is `debug`, forbidden otherwise; override lines exist in the served starter and each override region intersects a derived one; 1–3 regions of ≤ 3 lines; the hint quotes no starter line.
- Claude drafts the 9 blocks (regions as in the table, explanations and hints in vi/en); **the team reviews them** (a short sheet `docs/calibration/debug-meta-can-duyet.md`, like P1.5).

Commit `feat(content): debug metadata (bug regions, explanation, hint) for debug exercises`.

### Task 2: Storage and sync

**Files:** Modify `app/models/exercise.py`; create `alembic/versions/<rev>_exercise_debug_meta.py` (down_revision `b4e6a8c0d2f1`); modify `app/features/content/sync.py`; tests `tests/test_content_sync.py`.

- `exercises.debug_meta` JSON (JSONB on Postgres), nullable. Sync writes `{regions (resolved: override or derived), explanation_vi/en, hint_vi/en}` only when the `debug` block is approved; a draft block leaves the column as is.
- Test: approved block synced; draft block skipped with a reason; non-debug exercise keeps `null`.

Commit `feat(exercises): store debug metadata; content sync writes it`.

### Task 3: Hint and locate endpoints

**Files:** Create `app/features/attempts/debug.py` (service); modify `app/features/attempts/router.py`, `app/schemas/attempt.py` (`AttemptState`); tests `tests/test_debug_locate.py`.

- `POST /api/attempts/{id}/debug/hint` → `{"step": 1|2, "text": ...}` in the requested locale (`?locale=vi|en`); records `DEBUG_HINT {step}`. 409 after locating or after step 2; 400 on non-debug exercises; 409 once the attempt is submitted.
- `POST /api/attempts/{id}/debug/locate` body `{lines: int[], reason: str, skipped: bool}` → `{ok: true}`; records `LOCATE {lines, reason, skipped, hintsUsed}`. 409 if already located or submitted; 422 for lines outside the served starter, too many lines, reason too long.
- `AttemptState` gains `debug: {located: bool, hints_used: int, hints: [texts already bought]} | null` so a reload restores the step.
- Tests: full flow; every error case; hints restored after reload; the response never contains regions or the explanation.

Commit `feat(attempts): locate step for debug exercises (hints, location, reason)`.

### Task 4: Locate judge

**Files:** Modify `app/features/mentor/prompts.py` (`LOCATE_JUDGE_SYSTEM`), `app/features/scoring/judges.py` (`judge_locate`), `app/features/attempts/scoring_service.py` (run it at explain-back with the other judges; backfill support in `scoring/backfill.py`); tests `tests/test_scoring_judges.py`, `tests/test_submit_flow.py`.

- Input: the served starter with line numbers, the authored explanation (en), the selected lines, the reason. Output JSON `{level 0–3, evidence (quoted span)}`, anchored examples per level (the P1.4 style). Empty reason or skipped → level 0 without a call.
- Stored as `JUDGE {kind: "locate", level, evidence}`.

Commit `feat(scoring): judge the bug explanation of the locate step`.

### Task 5: Debugging indicators for debug exercises

**Files:** Modify `app/features/scoring/rubric.py`, `app/features/scoring/evidence.py` (expose `LOCATE`, `DEBUG_HINT`, the exercise's regions), `app/features/scoring/engine_v2.py` (pass `debug_meta`); tests `tests/test_scoring_rubric.py`, `tests/test_scoring_engine_v2.py`.

- `debugging(ev)`: if `ev.exercise_kind == "debug"` and a `LOCATE` event exists → the four indicators above; axis level = rounded mean; `evidence` quotes the selected lines and the judge's span; `reason` codes `located|partly_located|not_located|skipped` + the P1.4 fix reasons. Otherwise unchanged.
- Tests: each Located / Explained / Fixed level; skip; no `LOCATE` → identical to today on every existing debugging test. (Real sessions are checked in Task 8: a production dry-run rescore must show no change.)
- Note: "Fixed" is finer than the P1.4 rule (which gives 0 to anything not fixed); it only applies with a `LOCATE` event.

Commit `feat(scoring): debugging axis from locate, explain, fix and efficiency`.

### Task 6: Findings, templates and the reveal block

**Files:** Modify `app/features/feedback/diagnosis.py`, `templates.py`, `app/features/attempts/scoring_service.py` (`result_feedback`), `docs/api/feedback.md`; tests.

- Findings: `bug_located` (strength), `bug_not_located` (risk, medium; params `hints_used`), `bug_explained_well` (strength), `bug_explanation_weak` (risk, low). Templates vi/en, no absolutes, nothing that names the bug (the reveal block does that). Existing `bug_not_fixed`, `partial_fix`, `trial_and_error`, `quick_fix` stay for the fix part. The writer does not write these (`WRITTEN_CODES` unchanged).
- `feedback.debug` (only after submit): `{regions, selected, hit: bool[] per region, hints_used, skipped, explanation}` in the report locale.
- The team reviews the 4 new templates together with the Task 1 sheet.

Commit `feat(feedback): locate findings and the bug reveal`.

### Task 7: Frontend (CodeProve-UI session, via a spawn_task chip)

Contract: `docs/api/feedback.md` + the endpoints of Task 3. Locate view reusing the Daily Bug Hunt clickable-line component (read-only, multi-select up to regions + 1), reason box, two hint buttons with their cost stated, "skip" with a confirm; the editor unlocks after locating; a reload restores the step from `AttemptState.debug`; the Feedback page shows the reveal (the student's lines vs the real ones, explanation). **On debug exercises the free "Gợi ý / Hint" accordion (`SolveWorkspace`, the exercise's `hint`) is hidden until the student has located**: several of those hints name the bug (CP-102: "An unbounded dict is the leak") and would bypass the paid hint ladder. Tests and screenshots as in P1.6.

### Task 8: Ship

- Kiệt: merge, deploy, `alembic upgrade head` (in the container), `python -m app.features.content.sync --apply` after the team approved the 9 debug blocks (dry run first: it prints each block's reviewer).
- Claude: a dry-run `rescore --engine v2` must show **no change** (no old session has `LOCATE`); then one end-to-end debug attempt on production by Kiệt (locate → hint → fix → submit → Feedback reveal).

## Decisions for Kiệt

**Approved 2026-09-30:** all three as proposed.

1. The **rules** above (locate first, no live correctness, ≤ regions + 1 lines, 2 hints without the exact line, the level tables).
2. The **regions** for CP-012 and CP-102 (table): single region [5] and merged region [1, 4, 5].
3. **Skip** allowed (Located and Explained = 0) — proposed yes, so a stuck student can still fix and submit.
