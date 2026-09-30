# P2.4 "Review AI code" Step — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Measure verification skill in every session: after the student's own submit and before explain-back, they review 2 short "Ciel wrote this version" snippets of the same exercise, each either correct (the reference) or buggy (a validated mutant), and say "correct" or click the buggy line. The answer is revealed right away. The Verification axis gets this as an indicator next to the P1.4 in-session one, and the LLM-written in-session trap is removed.

**Architecture:** Server-side items (`REVIEW_ITEMS` event: which mutant or the reference, never sent before answering), one endpoint to fetch the items and one to answer an item (`REVIEW_ANSWER`, returns the reveal). `rubric.verification` adds a `review` part when answers exist; without them (old sessions, skipped) the P1.4 indicator is unchanged (decision 6). Findings, templates and a `feedback.review` block as in P2.2/P2.3; frontend in the CodeProve-UI session.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; `exercise_mutants` (3–5 validated mutants per exercise, `bug_line`, `note_vi/en`), `strip_comments`, `difflib`.

**Design:** `docs/superpowers/specs/2026-09-29-p2-design.md` (P2.4; decision 4 of 2026-09-30: the post-submit step).

---

## Facts this plan relies on (checked 2026-09-30)

- All 30 exercises have 3–5 mutants, each changing exactly one line of the reference and killed by ≥ 1 test (P1.1 validator), so "buggy" is checkable.
- Today's trap: 9 exercises have `verification_trap`; Ciel is told to put a subtle bug in one reply (`MENTOR_INJECT_SUFFIX`, `AI_REPLY.injectedError`). It is written by the LLM on the fly and can be harmless (P1.3, sim-02). Only engine v1 features read it; engine v2's Verification uses how the student handled Ciel's real code (observable in 11/39 golden sessions).
- A mutant differs from the reference by one line, so **any item shows the reference solution, correct or not**.

## Rules proposed in this plan

- **2 items per attempt**, each independently buggy with probability 0.55 (inside the design's 40–70%), mutants drawn without replacement; the student cannot infer one item from the other.
- **Display:** the code with comments stripped (as debug starters); the bug line is mapped to the stripped numbering (the line where stripped reference and stripped mutant differ).
- **Answer:** `{"verdict": "correct"}` or `{"verdict": "buggy", "line": n}`, once per item; the reveal comes back at once (buggy or not, the bug line, the mutant's note in the student's language).
- **Scoring per item:** buggy item: right line 1, flagged with a wrong line 0.5, said correct 0; correct item: said correct 1, flagged a line 0 (false alarm). Review level = 3 × mean over answered items. With both kinds present this is balanced accuracy (= (1 + H − F) / 2, the design's Youden H − F rescaled); a student's H − F over many sessions belongs to the P3 learner model.
- **Verification axis** = mean of `review` and the P1.4 in-session indicator when that one applies; with no answered item, unchanged.
- **Flow:** the UI shows the step between Submit and explain-back; the server does not force it (an old client just has no review part). Answers are accepted while the attempt is `submitted` (not after explain-back has scored it).
- **The in-session LLM trap is switched off** (`verification_trap` no longer injects; old events stay readable).

---

### Task 1: Review items

**Files:** Create `app/features/review/service.py`; tests `tests/test_review_items.py`.

- `make_items(ex, mutants, rng)` → 2 items `{kind: "correct" | "buggy", mutant_id?, code, bug_line?}` (stripped code, mapped line); `REVIEW_ITEMS` event stores kinds and mutant ids only.
- Tests: probability and no-replacement with a seeded RNG, line mapping with comments in the reference, every real exercise yields items whose mapped bug line is the changed line.

Commit `feat(review): review items from the reference and its mutants`.

### Task 2: Endpoints

**Files:** `app/features/attempts/router.py`, `app/schemas/attempt.py`, `service.SERVER_EVENT_TYPES` (+ `REVIEW_ITEMS`, `REVIEW_ANSWER`); tests `tests/test_review_api.py`.

- `GET /api/attempts/{id}/review?locale=` → `{items: [{index, code, answered, reveal?}]}`; creates the items on first call; 409 before submit.
- `POST /api/attempts/{id}/review/{index}` body `{verdict, line?}` → reveal `{buggy, bug_line, note, outcome: "hit" | "wrong_line" | "miss" | "correct_rejection" | "false_alarm"}`; 409 if answered, before submit or after scoring; 422 on a line outside the code.
- Tests: full flow, every error, the item code never contains a marker of which kind it is, reload returns answered items with their reveal.

Commit `feat(review): fetch and answer review items after submit`.

### Task 3: Verification axis

**Files:** `app/features/scoring/rubric.py` (`verification`), tests.

- With `REVIEW_ANSWER` events: `parts = {"review": level, "in_session": P1.4 level or None, "answered", "hits", "false_alarms", ...}`, axis = mean of applicable; reason codes kept from P1.4 for the in-session findings. Without: unchanged.
- Tests per outcome, mixed items, only review (no Ciel code → in-session N/A), no answers → unchanged.

Commit `feat(scoring): verification axis from the review step`.

### Task 4: Switch off the in-session trap

**Files:** `app/features/mentor/service.py` (no injection), `prompts.py` (keep the suffix for old-event docs or remove), tests `tests/test_mentor.py`.

Commit `refactor(mentor): drop the LLM-written trap; the review step replaces it`.

### Task 5: Findings, templates, report block, docs

- Findings: `review_caught` (strength: every item right), `review_missed_bug` (risk, medium), `review_false_alarm` (risk, low), `review_wrong_line` (risk, low). The P1.4 verification findings stay for in-session behaviour. Templates vi/en; team review sheet `docs/calibration/review-step-can-duyet.md`.
- `feedback.review` after scoring: the outcome, bug line and note per item (no code).
- `docs/api/feedback.md`: the step's contract (neutral examples only, no placeholders with content).

Commit `feat(feedback): review step findings and report`.

### Task 6: Frontend (CodeProve-UI, spawn_task chip)

After Submit, before explain-back: "Ciel viết phiên bản này. Code có đúng không?" per item, read-only code with clickable lines, buttons "Code đúng" / "Chọn dòng lỗi rồi xác nhận", the reveal after each answer, then explain-back. Feedback page section. Input fields: placeholder "Viết vào đây" only.

### Task 7: Ship

Merge, deploy (no migration), rescore dry run shows no change (no old session has `REVIEW_ANSWER`), end-to-end on production.

## Decisions for Kiệt

1. **Showing the reference after submit.** Every item, correct or buggy, is essentially the reference solution, so each student who submits sees it (and can share it). Hidden-test inputs and bug explanations are already shown after submit (P1.2, P2.2). (A, proposed) accept: full code, the review needs context to be fair. (B) show only a window of ~10 lines around the bug line (and a same-size window for correct items): less of the solution, but some bugs need the rest of the code to judge.
2. **Per-item scoring** above (hit 1, wrong line 0.5, miss 0; correct rejection 1, false alarm 0), level = 3 × mean.
3. **2 items, each buggy with p = 0.55** independently.
4. **Switch off the LLM-written trap** in this phase (Task 4).
