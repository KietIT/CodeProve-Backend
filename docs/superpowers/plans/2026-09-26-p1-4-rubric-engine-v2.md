# P1.4 Rubric Engine v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Score every axis on the same 0–3 levels the human raters used (`docs/calibration/huong-dan-cham.md`), from observable evidence, and fix the defects the golden set exposed (Verification scored backwards, Debug maxed without a fix, N/A applied inconsistently, Prompting by length heuristics).

**Architecture:** A new pure scoring module works on an `Evidence` bundle: events, prompt logs (Ciel's reply text), code snapshots, the submit suite and the LLM judges' verdicts. Each axis has 1–3 indicators; each indicator returns a level 0–3 (or N/A) with a short evidence string. Axis score = 20 × mean(level) / 3 over its applicable indicators, so reports keep their 0–20 columns. LLM verdicts are stored as `JUDGE` events when they are made, so a rescore never calls the LLM again. v2 replaces v1 only after it beats v1 on the golden set.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; the existing `MentorClient.judge` (JSON mode, temperature 0); calibration `analyze`.

**Evidence:** `docs/calibration/results-2026-09-26.md` (P1.3). Design: `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.4).

---

## Roadmap traceability

| Item | Task |
|---|---|
| [2] Rewrite each axis as an evidence-centred rubric (ECD), levels 0–3 with evidence | 1–6 |
| [+] Prompting rubric must not make skipping Ciel advantageous; a specific prompt reaches level 3 | 3 |
| [2] Show levels instead of decimals (backend: level per axis + tier) | 6 |
| [+] P1.3: Verification scored backwards (pasting AI code earns 20; no-code trap replies scored) | 4 |
| [+] P1.3: Debug scores 20 on debug exercises that were never fixed | 5 |
| [+] P1.3: raters applied N/A inconsistently; the rules must be enforced by the system | 5, 8 |
| [+] P1.3: Prompting only ρ = 0.57 with humans | 3 |
| [+] Validate v2 against the golden set before switching | 7 |
| (later) Ciel leaks full solutions; planted bug may be harmless | P2 (new Ciel trap), noted in Task 9 |

## Indicators (the team reviews this table before Task 3)

Decided 2026-09-26 (owner): **Ciel gave code but the student did not use it** (sim-06, sim-16, sim-20; raters had split 0–1 vs 2–3) is level 2, or 3 if the student questioned that code. The rating guide carries the same rule.


Level meanings follow the rating guide. "LLM" = anchored judge, JSON `{level, evidence}` with a quoted span.

| Axis | Indicator | Level rule |
|---|---|---|
| Understanding | explain-back (LLM, per answer, mean) | 0 wrong/none · 1 vague · 2 correct *what* · 3 correct *why* + edge case |
| Hypothesis | hypothesis quality (LLM on the best hypothesis) | 0 none · 1 vague · 2 correct approach · 3 approach + edge case/complexity; 3 only if logged before the first code edit, otherwise capped at 2 |
| Prompting | prompt quality (LLM, every prompt in one call, median) | 0 asks for the solution/off-topic · 1 short, vague · 2 specific with context · 3 says what was tried and asks for guidance. N/A: no prompt |
| Verification | AI-code handling (deterministic + one LLM flag) | N/A unless a Ciel reply contained a code block. *Pasted* = ≥ 70% of the block's non-blank lines appear in a later snapshot. Pasted, unchanged, suite fails at submit → 0 · pasted, unchanged, suite passes → 1 · pasted then changed some pasted lines → 2, or 3 if the suite then passes · not pasted → 2, or 3 if a later prompt questions the AI code (LLM flag) |
| Testing | submit suite (deterministic) | 0 never ran / submit < 50% · 1 submitted with visible tests failing · 2 visible pass, hidden fail · 3 all pass |
| Debugging | fix (deterministic) | N/A only for implement exercises without a real failing run. Debug exercises are never N/A. Not fixed at submit (suite fails) → 0 · fixed after ≥ 4 failing runs → 1 · 2–3 → 2 · 0–1 → 3 |

Overall: current weights (P1.3 decision) over the applicable axes; tier from overall as today.

---

### Task 1: Evidence bundle

`app/features/scoring/evidence.py`: `Evidence` dataclass (events, prompt logs with reply text and `created_at`, snapshots with `created_at`, final code, submit suite payload, exercise kind, judge verdicts from `JUDGE` events) and `async load_evidence(db, attempt)`. Helpers: `code_blocks(reply)`, `adopted(block, code) -> float` (share of the block's non-blank lines present in the code), `code_at(ts)` (latest snapshot at or before a time). Tests with small fixtures. Commit `feat(scoring): evidence bundle for rubric v2`.

### Task 2: Judges that store their verdicts

`app/features/scoring/judges.py` + prompts in `mentor/prompts.py`:
- `judge_prompts(problem, prompts)` → one call, per prompt `{level, evidence, questions_ai_code: bool, asks_for_solution: bool}`.
- `judge_hypothesis(problem, text)` → extends the existing hypothesis call (same request) with `level` and `evidence`; `correct` and `note` stay for the UI.
- `judge_explain(question, answer)` → `{level, evidence}`; the 0–20 `score` stays derived (`round(level × 20 / 3)`) so `VerificationAnswer.score` and old clients keep working. The short-answer guard stays (level 0 without a call).
- Explain-back and prompt verdicts are written as `JUDGE` events `{kind, levels, evidence, model}`; a hypothesis verdict goes into its own `HYPOTHESIS` event (`level`, `levelEvidence`) so each level keeps the time it was logged (the "before code" rule needs it). A missing or invalid level → the indicator is N/A, never an invented level. As built: the hypothesis and explain-back levels come from their existing v1 calls (extra JSON fields), so v2 adds one call per attempt (the prompts); a failed prompt call leaves prompts unrated instead of blocking scoring.
Anchors: 2 examples per level taken from the rating guide (not from the golden-set sessions, so validation stays fair). Tests with a fake client: parsing, clamping to 0–3, failure → N/A, events written. Commit `feat(scoring): anchored LLM judges with stored verdicts`.

### Task 3: Understanding, Hypothesis, Prompting indicators

`app/features/scoring/rubric.py`: pure functions over `Evidence` returning `Indicator(level: int | None, evidence: str)`. Rules as in the table; Prompting takes the median prompt level (a specific prompt reaches 3, so asking Ciel well is never worse than not asking). Tests per level. Commit `feat(scoring): rubric v2 understanding, hypothesis and prompting`.

### Task 4: Verification indicator

Rules as in the table, from reply code blocks, snapshots and runs. Golden-set regressions become tests (built as fixtures, not DB rows): pasted AI code unchanged (sim-18 failing → 0; sim-02 passing → 1), AI code not used (sim-16, sim-20, sim-26 → 2), trap reply without code (sim-09, sim-27 → N/A). Commit `feat(scoring): rubric v2 verification from AI-code handling`.

### Task 5: Testing and Debugging indicators, enforced N/A

Rules as in the table. Tests include a debug exercise whose buggy starter passes the visible tests and is submitted unfixed (sim-19, sim-24 → 0, not 20) and a debug exercise with no failing run that is fixed (→ 3). Commit `feat(scoring): rubric v2 testing and debugging`.

### Task 6: Engine v2 and report shape

`score_attempt_v2(evidence)` → same dict as v1 plus `levels` (axis → 0–3 or None) and `evidence` (axis → indicator evidence strings). `report_columns` stores levels and evidence in `feedback` (P1.5 builds on them). Scoring at explain-back calls the judges, then v2. `SCORING_ENGINE` setting (`v1` default until Task 7 passes, then `v2`). v1 stays importable for comparison until P1.7. Tests: the flow end to end with a fake judge. Commit `feat(scoring): engine v2 behind a setting`.

### Task 7: Validate on the golden set, then switch

`python -m app.features.scoring.rescore --engine v2 --keys keys.json --out engine_v2.json` (dry run; calls the judges once for attempts that have no `JUDGE` events yet, then stores them). Owner runs it on EC2 and sends `engine_v2.json`; Claude runs `analyze` with it.
Pass criteria (else iterate on Tasks 3–5): Verification Spearman > 0.3 and N/A agreement ≥ 90%; Debugging N/A agreement ≥ 95% and Spearman ≥ 0.69; Prompting Spearman ≥ 0.7; no other axis more than 0.05 below v1; overall Spearman ≥ 0.90.
Then owner sets `SCORING_ENGINE=v2` and runs `rescore --engine v2 --apply` for all reports.

### Task 8: Rating page follows the N/A rules

`docs/calibration/trang-hieu-chuan-b.html`: hide the N/A option where the rules forbid it (Debugging on debug exercises; Prompting when there are prompts; Verification when no reply contains code). Used for the real-session round before P1.7.

### Task 9: Hand-off notes for P2

Add to the roadmap's P2 "new Ciel trap" section: the planted bug must come from the validated mutant bank (fails ≥ 1 test), and full-solution replies must be blocked in code (e.g. a reply whose code block defines the entry point and passes the visible tests is withheld), both evidenced by sim-02.

## Who does what

| Step | Who |
|---|---|
| Review the indicator table | 4 members (15 min) |
| Tasks 1–6, 8, 9 | Claude |
| Merge, deploy, run the v2 dry run on EC2, send `engine_v2.json` | Kiệt |
| Validation report, then `SCORING_ENGINE=v2` + rescore | Claude, then Kiệt |
