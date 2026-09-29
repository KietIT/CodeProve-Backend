# P1.7 Axis Weight Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Choose the six axis weights of the overall score with evidence: compare the current weights, equal weights, the team's AHP weights and constrained-regression weights by how well the resulting overall score agrees with the team's holistic overall ratings on the golden set, pick one by a rule fixed in advance, commit the choice and the evidence, and rescore.

**Architecture:** A new analysis module `app/features/calibration/weights.py` (pure Python, like `agreement.py` and `ahp.py`: no numpy/scipy) reads the same data directory as `analyze.py` (rater exports + `engine.json`). It recomputes each session's overall from the engine v2 axis scores under each candidate weight set using the **same formula as the engine** (weighted mean over applicable axes, weights renormalised when an axis is N/A), then measures agreement with the human mean overall level. The regression weights are fitted and evaluated with leave-one-out cross-validation, because n ≈ 40 would otherwise flatter a fitted set. The engine's overall formula moves into one shared function so the analysis and production can never drift apart.

**Tech Stack:** Python 3, pytest; existing `agreement.icc2`, `agreement.spearman`, `ahp` module, `analyze.load_dump`.

**Inputs:** P1.3 golden set and ratings (`calibration-private/golden/`, `exports/`: 39 simulated sessions, 4 raters, AHP from Kiệt, Phát, Trung), engine v2 (P1.4, live), P1.3 results (`docs/calibration/results-2026-09-26.md` §3: current 0.920, equal 0.911, AHP 0.874 on the **v1** engine). Design: `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.7).

---

## Decisions for Kiệt before Task 1

**Decided 2026-09-29:** 1 = B (the 39 simulated sessions only, limitation stated in the results), 2 = A (AHP of Kiệt, Phát, Trung), 3 = floor 5%. The `--exclude-email-like` export change in Task 1 is therefore not needed.

1. **Which sessions.** P1.3 recommended adding ≥ 15 real sessions because the 39 simulated ones were written to spread the levels and may overstate agreement.
   - (A, recommended if the data exists) Export 15–20 real student sessions with `app.features.calibration.export`, the team rates them on the same offline page (≈ 1–1.5 h each), then analyse 39 + real. Needs ≥ 15 sessions from students outside the team; Task 1 counts them first.
   - (B) Use the 39 simulated sessions only; state the limitation in the results.
2. **Minh's AHP** is still missing. (A) Proceed with 3 members (the AHP set is one candidate among four, and P1.3 already showed it ranked worst). (B) Wait for Minh.
3. **Regression floor.** Constrained regression may push an axis to 0, which would tell students that axis does not count. Proposed: each weight ≥ 5%, weights sum to 1.

## Selection rule (fixed before looking at results)

- **Primary metric:** Spearman between the recomputed overall and the human mean overall level (fixed sets: all sessions; regression: leave-one-out predictions).
- **Secondary:** ICC(2,1) absolute agreement between the engine's tier (0–3 from the current cutoffs 50 / 70 / 85) and the human mean level, and exact tier agreement (%).
- **Uncertainty:** 2 000-sample paired bootstrap of ΔSpearman against the current weights (95% interval).
- **Choice:** keep the **current** weights unless a candidate beats them by ≥ 0.02 Spearman **and** its bootstrap interval of the difference excludes 0. Among candidates that qualify, prefer the simpler one (equal < AHP < regression). "Prefer the simpler set when differences are small" (design).
- Tier cutoffs are not changed in P1.7; if the tier agreement shows a systematic offset (e.g. engine one tier above humans on most sessions), it is reported as a follow-up decision.

---

### Task 1: Fresh inputs (Kiệt, EC2) and a data check (Claude)

- `engine.json` for the golden set from the **current** engine v2 (the one in `golden/engine_v2.json` predates the debug rule change and the P1.5 deploy):
  `docker exec codeprove_backend python -m app.features.scoring.rescore --engine v2 --keys /tmp/keys.json --out /tmp/engine_v2.json` (dry run, writes nothing to the DB), then `docker cp` out and put it in `calibration-private/golden/`.
- If decision 1 = A: the export today only has `--email-like` (include), so Claude first adds `--exclude-email-like` (repeatable: the simulated `calib.sim%@example.com` and the team's own accounts, which Kiệt lists) with a test; commit `feat(calibration): exclude accounts from the golden-set export`. Kiệt then runs the export on EC2 to count real sessions; if ≥ 15, export 20 with `--keys-out`, and Claude builds the rating page the same way as P1.3 (the team rates them; ratings go to `exports/`).
- Claude checks: every session in `keys.json` has an engine entry; axis scores in 0–20; overall recomputed with the current weights equals the stored overall (± 0.01).

### Task 2: One overall formula for engine and analysis

**Files:** Modify `app/features/scoring/engine_v2.py`, `app/features/scoring/engine.py`; test `tests/test_scoring_engine_v2.py`.

- Add `weighted_overall(axes: dict[str, float | None], weights: dict[str, float]) -> float` (in `engine.py`, next to `WEIGHTS`): the existing formula (`5 × Σ w_a/Σw_active × score_a` over non-null axes, 0 when none, clamped 0–100, rounded to 2). `score_attempt` (v1) and `score_attempt_v2` call it with `WEIGHTS`.
- Tests: an N/A axis renormalises the rest; all N/A → 0; same results as before on the existing engine tests (no behaviour change).

Commit `refactor(scoring): one weighted_overall for engine v1, v2 and calibration`.

### Task 3: Candidate weight sets and agreement metrics

**Files:** Create `app/features/calibration/weights.py`; test `tests/test_calibration_weights.py`.

- `candidates(ahp_answers) -> dict[str, dict[str, float]]`: `current` (`WEIGHTS`), `equal`, `ahp` (group AIJ of every member with an answer set, via `analyze.ahp_section`), `ahp_consistent` (only when it differs).
- `human_overall(dump) -> dict[session, float]`: mean overall level (0–3) over raters (same rule as `analyze.py`).
- `evaluate(overall_by_session, human) -> {"spearman", "icc", "tier_exact", "n"}`: tier level via `tier_for` cutoffs mapped to 0–3.
- `bootstrap_delta(a, b, human, samples=2000, seed=0)`: paired bootstrap of Spearman(a) − Spearman(b) → (mean, low, high).
- Tests: a synthetic set where the humans follow one axis exactly → a weight set concentrated on that axis wins; bootstrap is deterministic with the seed; tier mapping at the cutoffs (49.99 → 0, 50 → 1, 85 → 3).

Commit `feat(calibration): weight candidates and agreement metrics`.

### Task 4: Constrained regression with leave-one-out

**Files:** Modify `weights.py`; tests.

- `fit_weights(sessions, human, floor=0.05) -> dict[str, float]`: maximise the Pearson correlation between `weighted_overall` and the human mean (scale-free, so no intercept is needed) over the simplex with every weight ≥ `floor`. Projected gradient ascent with a numeric gradient (6 parameters, ≈ 40 sessions: milliseconds), several starts (current, equal, each axis-heavy corner), keep the best.
- `loo_predictions(sessions, human, floor)`: for each session, fit on the others, predict it. Also report the weights fitted on all sessions (the set that would ship) and their spread across the LOO folds (min–max per axis), which shows how stable they are.
- Tests: recovers known weights on synthetic data within 0.03; respects the floor and sums to 1; LOO never sees the held-out session (fit function called with n − 1 rows).

Commit `feat(calibration): constrained-regression weights with leave-one-out`.

### Task 5: Report and CLI

**Files:** Modify `weights.py` (`render`, `main`); tests.

`python -m app.features.calibration.weights --data DIR --out FILE.md [--floor 0.05]`: a Markdown report in Vietnamese like `analyze.py`: the candidate weights table; per candidate Spearman, ICC, tier agreement; ΔSpearman vs current with bootstrap interval; regression weights with LOO spread; the selection rule applied, naming the chosen set; the sessions whose tier would change under the chosen set.
Tests: the report names the chosen set by the rule on a synthetic dump; a missing AHP section does not crash.

Commit `feat(calibration): weight selection report`.

### Task 6: Run, results doc, decision (checkpoint)

- Claude runs the CLI on the private data, writes `docs/calibration/weights-2026-09-xx.md` (summary, table, limits: raters are the builders, simulated sessions, Minh's AHP), and gives Kiệt the recommendation from the rule.
- **Kiệt decides.** If the current weights stay: commit the evidence, no rescore, P1.7 done.

### Task 7: Apply new weights (only if they change)

- Change `WEIGHTS` in `engine.py`; update the tests that pin overall values (`test_scoring_engine.py`, `test_scoring_engine_v2.py`, `test_rescore.py`, `test_scoring_backfill.py`, `test_calibration_*`). Note: `diagnosis._AXIS_RANK` uses `WEIGHTS`, so the order of same-severity findings may change (expected).
- Docs: roadmap / P1 design note of the chosen weights and the evidence file.
- Kiệt deploys, runs `rescore --engine v2` (dry run: shows every overall and tier change), sends the output; then `--apply`. Every student's overall may move, so Kiệt decides whether to tell users.

Commit `feat(scoring): axis weights chosen on the golden set (P1.7)`.

## Who does what

| Step | Who |
|---|---|
| Decisions 1–3, approve this plan | Kiệt |
| Task 1 exports on EC2 (and the team rates real sessions if 1 = A) | Kiệt, team |
| Tasks 2–5, analysis, results doc | Claude |
| Choice of weights (Task 6), deploy and rescore (Task 7) | Kiệt |
