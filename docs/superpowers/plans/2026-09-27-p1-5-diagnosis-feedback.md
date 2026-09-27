# P1.5 Diagnosis and Actionable Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the generic "Improve your prompting." feedback with specific, evidence-backed findings, each explained as *what happened / why it matters / how to improve / what to try next*, in the student's language. Every finding comes from the rubric v2 evidence, so the feedback can never criticise something the session did not show.

**Architecture:** Two layers under `app/features/feedback/`:
1. **Diagnosis (deterministic):** `diagnose(result, evidence)` turns the engine v2 result (levels, reason codes, evidence quotes) and the submit suite into a ranked list of **findings**. Each finding has a stable `code`, `axis`, `kind` (strength / risk), `severity`, `params` (e.g. failed test categories) and `evidence` (a quote or a fact).
2. **Writing (LLM with fallback):** one call at explain-back turns the findings, the problem, the final code and the explain-back answers into the four texts per finding. The output is validated: only the given codes, no invented critique, no long code (no solution leak), `try_next` only from a supplied list. On failure or timeout, localized templates per code are used.

The report stores `feedback.diagnosis` next to the current fields (kept until P1.6 switches the UI). The frontend renders from codes, params and texts, and never parses English sentences.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; `MentorClient.judge` (JSON mode, temperature 0) on the current `OPENAI_MODEL` (P1 design decision 4).

**Inputs:** rubric v2 (`app/features/scoring/rubric.py`, `engine_v2.py`, P1.4). Design: `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.5).

---

## Roadmap traceability

| Item | Task |
|---|---|
| [1] Feedback is generic ("Improve your prompting."): diagnosis layer from evidence | 1 |
| [1] LLM-written actionable feedback: what happened / why it matters / how to improve / try next | 3, 4 |
| [1] Template fallback when the LLM fails | 2, 4 |
| [1] Frontend stops regex-matching English notes: feedback carries codes and params | 1, 5, 7 (UI itself: P1.6) |
| [+] The LLM may only explain findings it was given (no invented critique) | 4 |
| [+] Feedback must not leak the solution (it is shown right after submit) | 4, 6 |
| [+] Feedback in the language the student used (vi/en) | 2, 5 |
| [+] Checked on the golden set before release | 6 |

## Finding catalog (the team reviews this before Task 2)

Severity: `high` blocks the skill the platform measures, `medium` costs a level, `low` is polish. The report shows at most **3 risks** (highest severity first, then axis weight) and **2 strengths**.

| Code | Axis | Kind | Trigger (rubric v2) | Severity | Params |
|---|---|---|---|---|---|
| `explain_missing` | understanding | risk | level 0 | high | |
| `explain_shallow` | understanding | risk | level 1–2 (vague, or says what but not why) | medium | |
| `explain_strong` | understanding | strength | level 3 | | |
| `no_hypothesis` | hypothesis | risk | reason `no_hypothesis` | medium | |
| `hypothesis_vague` | hypothesis | risk | level 1 | low | |
| `hypothesis_after_code` | hypothesis | risk | reason `after_code` | low | |
| `hypothesis_strong` | hypothesis | strength | level 3 | | |
| `asked_for_solution` | prompting | risk | any prompt flagged `asks_for_solution` | high | count |
| `prompts_vague` | prompting | risk | level ≤ 1 (and not `asked_for_solution`) | medium | |
| `prompts_strong` | prompting | strength | level 3 | | |
| `pasted_ai_failing` | verification | risk | `pasted_unchanged`, level 0 | high | |
| `pasted_ai_unchecked` | verification | risk | `pasted_unchanged`, level 1 | medium | |
| `adapted_ai_code` | verification | strength | `pasted_changed`, level 3 | | |
| `questioned_ai_code` | verification | strength | reason `questioned` | | |
| `never_ran_tests` | testing | risk | reason `never_ran` | high | |
| `submitted_failing` | testing | risk | level 0–1 with runs | high | passed, total |
| `hidden_edge_failed` | testing | risk | level 2 | medium | failed_categories |
| `all_tests_passed` | testing | strength | level 3 | | |
| `bug_not_fixed` | debugging | risk | reason `not_fixed` | high | |
| `partial_fix` | debugging | risk | reason `partially_fixed` | medium | failed_categories |
| `trial_and_error` | debugging | risk | fixed, level 1 | medium | failing_runs |
| `quick_fix` | debugging | strength | fixed, level 3 | | |
| `integrity_flags` | overall | risk | integrity multiplier < 1 | high | flags |

---

### Task 1: Diagnosis

`app/features/feedback/diagnosis.py`: `Finding` (pydantic: `code, axis, kind, severity, params, evidence`) and `diagnose(result, evidence) -> list[Finding]`, pure, rules exactly as in the catalog, ranked and trimmed (3 risks, 2 strengths). Needs `rubric` to also expose the prompt flags and the failing categories it already reads (no second parsing). Tests: one per code with a small `Evidence`; ranking and trimming; an N/A axis yields no finding; the P1.3 regressions keep their meaning (sim-02 → `pasted_ai_unchecked`, sim-18 → `pasted_ai_failing`, sim-19 → `partial_fix`). Commit `feat(feedback): deterministic diagnosis from rubric v2`.

### Task 2: Templates (fallback text)

`app/features/feedback/templates.py`: for every code, vi and en texts for the four fields, with `{params}` placeholders (e.g. "Test ẩn nhóm {failed_categories} còn fail"). `try_next` in templates names the suggested exercise from Task 3 generically. Tests: every catalog code has both locales and all four fields; placeholders render with the params the diagnosis produces; missing params never crash. Texts drafted by Claude, reviewed by the team with the catalog. Commit `feat(feedback): localized templates per finding`.

### Task 3: Next-exercise candidates

`app/features/feedback/next_exercise.py`: `candidates(db, user, exercise, findings) -> list[str]` (≤ 3 exercise codes): not yet solved by the user, same or next level, preferring the same `category`, and for debugging risks a debug exercise. Deterministic, so the LLM can only pick from it. Tests with a small seeded catalog. Commit `feat(feedback): next-exercise candidates`.

### Task 4: LLM writer with validation

`app/features/feedback/writer.py` + `FEEDBACK_WRITER_SYSTEM` in `mentor/prompts.py`. Input: locale, problem summary, findings (code, axis, kind, params, evidence), final code (≤ 60 lines), explain-back Q&A, candidates. Rules in the prompt: write only about the listed findings, quote the evidence, one or two sentences per field, no code longer than 2 lines, never the full solution, `try_next` ∈ candidates or empty. Output JSON `{"items": [{"code", "what_happened", "why_it_matters", "how_to_improve", "try_next"}]}`.
Validation: codes ⊆ given codes; each field non-empty and ≤ 400 chars; code fences removed if longer than 2 lines; `try_next` must be a candidate; wrong locale is not detectable cheaply, so it is not checked. Any item that fails falls back to its template; a failed call (error/timeout 12 s) falls back entirely. Each finding records `source: "llm" | "template"`. Tests with a fake client: happy path, unknown code dropped, a long code block stripped, `try_next` outside candidates cleared, timeout → all templates. Commit `feat(feedback): LLM writer with validation and template fallback`.

### Task 5: Wire into scoring and reports

- `/submit` stores the locale in the `SUBMIT` event (`{"locale": "vi" | "en"}`); explain-back reads it (default `vi`).
- After engine v2 scores, `diagnose` + `candidates` + `write` run; the report stores `feedback.diagnosis = {"version": 1, "locale", "findings": [{...finding, "text": {...}, "source"}]}`. The v1 fields (`strengths`, `risks`, `per_axis`) stay until P1.6.
- `GET /report` returns it unchanged. With engine v1 there is no diagnosis (the key is absent).
- Rescore recomputes the findings and keeps the stored text of a finding whose code and params are unchanged; otherwise it uses the template (a rescore never calls the writer).
Tests: explain-back returns `feedback.diagnosis` in the student's locale; the writer failing still returns a report; rescore keeps texts. Commit `feat(feedback): diagnosis in reports`.

### Task 6: Quality check on the golden set

`python -m app.features.feedback.preview --keys keys.json --out feedback_preview.json` (EC2, owner): the diagnosis and written feedback for the 39 golden sessions, without touching the reports. Claude runs automatic checks (codes match the diagnosis, no code block > 2 lines, no line of the reference solution longer than 20 characters copied verbatim, `try_next` valid) and builds a review sheet (`docs/calibration/feedback-review.md`) of 12 sessions across levels. Each team member rates each finding: accurate? specific to this session? actionable? leaks the answer?
Pass: 0 leaks; ≥ 80% of findings rated accurate and actionable; otherwise fix the prompt or the catalog and repeat.

### Task 7: API note for P1.6

`docs/api/feedback.md`: the `feedback.diagnosis` shape, the finding codes and params, locale handling, and the rule that the UI renders texts and codes, never parses English notes. It is the contract for the P1.6 frontend plan (`codeprove-web`).

## Cost and latency

One extra LLM call per submitted attempt (the writer), at explain-back, with a 12-second timeout. Explain-back already waits for its judges, so the student sees the report a few seconds later than today; on timeout the templates answer instantly.

## Who does what

| Step | Who |
|---|---|
| Review the finding catalog (Task 1 table) and the template texts (Task 2) | 4 members |
| Tasks 1–5, 7 | Claude |
| Merge, deploy, run the preview on EC2, send `feedback_preview.json` | Kiệt |
| Automatic checks + review sheet | Claude |
| Rate the 12-session review sheet | 4 members (~30 min) |
