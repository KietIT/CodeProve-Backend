# P2.6 Recalibration of the New Indicators — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Check with the team's ratings that the P2 mechanics score what humans would: the Debugging axis of debug exercises (locate → fix, P2.2), the Testing axis with student-written tests (P2.3) and the explain-back judge fix (P2.5); then re-run the P1.7 weight check on the enlarged golden set.

**Architecture:** Reuse the P1.3 pipeline end to end: scripted sessions played by the simulator against production, exported anonymised, rated on the offline page B, analysed with `analyze.py` and `weights.py`. P2.6 extends each piece with the new evidence instead of building new tools.

**Tech Stack:** `app/features/calibration/{simulate,export,analyze,weights}.py`, `docs/calibration/sim/` scripts and profiles, `docs/calibration/trang-hieu-chuan-b.html`, `docs/calibration/huong-dan-cham.md`.

**Design:** `docs/superpowers/specs/2026-09-29-p2-design.md` (P2.6). P2.4 was skipped, so Verification is not re-calibrated here.

---

### Task 1: Simulator actions for the new mechanics

`simulate.py`: new step actions `hint` (debug hint), `locate` (`lines`, `text` = reason, or `skipped`), `tests` (a list of student tests, saved with `PUT /tests`; optional `check: true` calls `/tests/check` per test). Validation: locate lines inside the served starter; test inputs pass the allow-list; `tests` only on exercises with the tab. Script ids `sim-41`…`sim-60`. Tests with a fake API, as for the P1.3 actions.

### Task 2: 20 scripted sessions with intended profiles

- **10 debug sessions** (the 9 debug exercises, one twice): located first try / after 1–2 hints / wrong line / skipped; reason strong / vague / wrong; fixed / partial / not fixed; few or many failing runs.
- **10 tests-tab sessions** (junior, senior and fresher exercises with the tab): no tests (junior and fresher), invalid tests, one category only, tests that miss mutants, a strong set.
- **2 of them reproduce the P2.5 case:** a confident explanation of code the tests show wrong (a lock created inside the function), to check the judge now caps it.
- Intended per-axis levels in `profiles.json`, as in P1.3 (for the intended-vs-human check only, never as the answer).

### Task 3: Export, rating page and rating guide

- `export.py`: add the locate step (lines, reason, hints used, skipped), the student tests (each with validity, covered categories, mutants caught / total and the missed notes) and the bug reveal, so raters see what the engine saw.
- Page B shows them next to the session (debug: the starter with the selected lines; tests: a table).
- `huong-dan-cham.md`: Debugging on debug exercises and Testing with student tests rated on the same 0–3 descriptors as the engine's parts (P2.2 and P2.3 level tables), plus when "N/A" applies. The team skims the new rows before rating.

### Task 4: Run and rate (Kiệt and the team)

Kiệt runs the simulator on production (existing sim accounts), exports, sends the files; the team rates the 20 sessions independently on page B (≈ 1–1.5 h each).

### Task 5: Analysis, results, decisions

- `analyze.py` on the 20 sessions: weighted κ between raters and engine-vs-human Spearman for Debugging and Testing; the P2.5 sessions' explain levels.
- `weights.py` on all 59 sessions (39 + 20) with the P1.7 rule.
- Results doc `docs/calibration/results-p2-<date>.md`; any level-table change proposed as a decision, not applied silently.

## Pass criteria (proposed)

κ ≥ 0.6 between raters and Spearman engine vs mean human ≥ 0.7 on Debugging (debug exercises) and Testing (student tests); the P2.5 sessions rated at most level 1 on understanding by the engine. Otherwise the level tables are adjusted and the affected part re-checked.

## Decisions for Kiệt

1. **20 new sessions** (10 debug, 10 tests-tab), rated by the team (≈ 1–1.5 h each); or skip P2.6 now and go to P3, accepting the new indicators without a human check.
2. **Run them on production** with the existing simulated accounts, as in P1.3.
3. **The pass criteria** above.
