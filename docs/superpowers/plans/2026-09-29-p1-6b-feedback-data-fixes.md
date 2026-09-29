# P1.6b Feedback Data Fixes (backend) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Two problems students see on the new Feedback page (found on production, attempt 233): (1) failing-test inputs are raw harness expressions (`(lambda NS, to_list: …)(lambda v, n=None: __import__('types').SimpleNamespace(…))`) in 17 of 31 exercises; (2) the integrity badge can be yellow/red with no finding that explains it.

**Owner decisions (Kiệt, 2026-09-29):** integrity: explain only, no score change; readable inputs: Claude drafts them, the team reviews them through the P1.1 content review before sync.

**Frontend:** no change needed (the page renders `failures[].input` as text and any finding code). The frontend copy fixes of the same check are in `codeprove-web/docs/superpowers/plans/2026-09-29-p1-6b-feedback-fixes.md`.

**Branch / worktree:** `fix/p1-6b-feedback-data` from `origin/main` (ed4bf59), in `.claude/worktrees/p1-6b-feedback-data`.

---

## Findings behind this plan

- `failures[].input` is `TestCase.input_data`, the expression the sandbox `eval`s (`sandbox/runner.py`). For linked lists, trees and similar, the content files build objects inline, so the expression is unreadable. Affected (tests with `lambda`/`__import__` / total): CP-002 7/8, CP-009 5/8, CP-012 3/7, CP-101 9/9, CP-102 7/7, CP-103 6/8, CP-104 6/8, CP-106 7/7, CP-108 6/7, CP-109 7/7, CP-110 1/9, CP-201 8/8, CP-203 7/7, CP-204 6/8, CP-206 7/7, CP-207 7/9, CP-208 9/9 (≈ 108 tests). Test descriptions are unique within each exercise.
- `feedback.submit_tests` is rebuilt from the `SUBMIT_TESTS` event payload (`_submit_tests_view`), which stored the raw input at submit time. Mapping at read time fixes every stored report without rescoring or rewriting events.
- Integrity: `integrity_status` counts `paste_flags + focus_lost + tab_hidden + window_blur + fullscreen_exits` (≥ 4 red, ≥ 1 yellow), but `integrity_multiplier` and the `integrity_flags` finding only use `paste_flags` and legacy `FOCUS_LOST`. New sessions emit `TAB_HIDDEN` / `WINDOW_BLUR` / `FULLSCREEN_EXIT`, so a student who switched tabs 4 times gets "Bị gắn cờ" with no explanation and no penalty.

---

### Task 1: `display` input in content, model and sync

**Files:** `app/features/content/schema.py`, `app/features/content/validate.py`, `app/models/test_case.py`, new migration (down_revision `b4e6a8c0d2f1`), `app/features/content/sync.py`, tests.

- `ContentTest.display: str | None` (min length 1): a readable call, e.g. `reverse_list([1, 2, 3])` where the list stands for the linked list (the exercise statement says so), `build_tree([2, 1, 3])`.
- Validator: a test whose `input` contains `lambda` or `__import__` must have `display`; `display` must not contain them.
- `TestCase.display_input: Text | None` + migration; `sync` writes it.
- Tests first: schema accepts/rejects; sync stores `display_input`.

Commit `feat(content): readable display input for harness-built tests`.

### Task 2: Readable inputs on the report

**Files:** `app/features/attempts/submit_tests.py` (or a small helper next to it), `app/features/attempts/router.py` (report + explain-back), tests.

- Helper `with_display_inputs(db, exercise_id, submit_tests)`: for each failure, when the exercise's test with the same `description` has `display_input`, replace `input` with it (clipped like today). Applied where the report is returned (`GET /report`, explain-back response). The stored event keeps the raw expression (the sandbox and analytics need it).
- New submissions go through the same path, so there is one rule.
- Tests first: failure with a matching test → display text; no `display_input` → unchanged; unknown description → unchanged.

Commit `feat(report): show readable test inputs on the feedback page`.

### Task 3: Draft display inputs for the 17 exercises

**Files:** `content/exercises/CP-*.json` (17 files).

- For each harness test, add `display` derived from the `input` expression (the values it builds), in the call style of the exercise statement. Script-assisted where the pattern is regular (linked-list `NS(...)` chains, tree builders), hand-written otherwise.
- Each touched file: `review.status` → `draft`, `author` stays `claude`, `reviewer` unchanged (the same member re-approves). Sync skips drafts, so production keeps today's data until each file is approved.
- Review sheet for the team: `docs/calibration/display-inputs-review.md`, one table per exercise (description, raw input, proposed display), so reviewers check values without reading lambdas.
- Validator (`validate_content`) must still pass for every file.

Commit `content: draft readable display inputs for 17 exercises`.

**Team step:** each reviewer checks their files and sets `status: approved`. Then `python -m app.features.content.sync --apply` on production.

### Task 4: Explain every integrity badge

**Files:** `app/features/feedback/diagnosis.py`, `app/features/feedback/templates.py`, `docs/api/feedback.md`, tests.

- New finding code `integrity_signals` (axis `overall`, kind `risk`), added when `integrity_status` is yellow/red and `integrity_multiplier == 1.0` (no penalty). Severity: red → `medium`, yellow → `low`, so it never displaces a high-severity learning risk; `integrity_flags` (penalised) is unchanged.
- Params: counts of `paste`, `focus_lost`, `tab_hidden`, `window_blur`, `fullscreen_exits` (non-zero only). Extend `_SIGNALS` with "rời tab {n} lần" / "switched tabs {n} time(s)", "chuyển sang cửa sổ khác {n} lần" / "switched windows {n} time(s)", "thoát toàn màn hình {n} lần" / "left full screen {n} time(s)". `integrity_flags` also lists the new signals when present.
- Template (vi/en, four fields, draft for team review): what happened "Hệ thống ghi nhận {signals} trong phiên làm bài. Điểm của bạn không bị trừ vì các tín hiệu này."; why it matters, how to improve, try next reuse the `integrity_flags` wording without "điểm bị giảm". Reviewed like the P1.5 templates (round in `docs/calibration/`) before merge.
- Contract: add `integrity_signals` to the finding table in `docs/api/feedback.md`.
- Tests first: red status + multiplier 1.0 → `integrity_signals` (medium) with tab counts; multiplier < 1 → `integrity_flags` only; green → neither.
- After deploy: `python -m app.features.scoring.rescore --engine v2 --apply` so stored reports get the finding (refresh keeps unchanged LLM lines).

Commit `feat(feedback): explain integrity badges that carry no penalty`.

### Task 5: Verify and ship

- `pytest`, content validator on all files.
- PR `fix/p1-6b-feedback-data` → `main` after the template review. Deploy, `alembic upgrade head`, content sync (approved files only), rescore v2 `--apply`.
- Check on production (read-only, dev account): attempt 233 shows readable inputs once CP-002 is approved and synced, and an `integrity_signals` card.

## Who does what

| Step | Who |
|---|---|
| Approve this plan | Kiệt |
| Tasks 1–4 code, drafts, review sheets | Claude |
| Review display inputs (per file) and the new template | Team (Kiệt, Trung, Minh, Phát) |
| Merge, deploy, migrate, sync, rescore | Kiệt |

## Out of scope

- Penalising tab/window/fullscreen signals (owner decision: explain only).
- `never_ran_tests` next to submit results: correct (the student ran no test before submitting; the submit suite runs automatically).
- The Debugging N/A wording: frontend copy fix (see the frontend plan).
