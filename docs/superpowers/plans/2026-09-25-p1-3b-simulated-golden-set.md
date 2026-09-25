# P1.3b Simulated Golden Set Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce the ~40 golden-set sessions without waiting for classmates: Claude authors 40 varied session scripts and a simulator plays them through the **production API** (real sandbox, real Ciel, real hypothesis/explain-back judges, real scoring engine). Then finish P1.3: seed the rating page, add the analysis CLI, and hand the owner exact export instructions.

**Architecture:** A small async HTTP simulator (`app/features/calibration/simulate.py`, httpx) runs scripted "students" in real time, concurrently, against the public API, exactly as the web client would (same endpoints, same client events). Explain-back is a second phase: the simulator stops after Submit and saves the generated questions; Claude writes the answers per persona; phase 2 posts them and the engine scores. Scripts and their intended profiles stay **outside the repo** until the team finishes rating (the raters have repo access). Export gains a filter so the golden set is exactly the simulated accounts, plus a private id map so the analysis can join ratings, engine scores and intended profiles.

**Tech Stack:** Python 3.12, httpx (already a dependency), pydantic v2, pytest with `httpx.MockTransport`; existing calibration modules (ahp, agreement, export); the Artifact page and `ArtifactData`.

**Supersedes:** the "classmates generate sessions" step of `2026-09-24-p1-3-ahp-and-golden-set.md` (owner decision 2026-09-25). The invitation doc stays for a later round of real sessions.

---

## Roadmap traceability

| Item | Task |
|---|---|
| [2] Golden set of 30–50 human-rated sessions (now: 40 simulated, played through the real system) | 1–7 |
| [2] Axis weights v1 via AHP, benchmarked against equal weights | 8, 9 |
| [2] Owner: "build all 40 sessions, diverse; then finish the AHP tool and golden set; tell me what to export and send" | 1–9 |
| [+] Raters must stay blind to the intended profiles and to engine scores | 4, 6, 7 |
| [+] Simulated data must not be mistaken for real students (production metrics, later analyses) | 1, 5, 10 |

## Honest limitations (written into the results report)

- The sessions are authored by one writer (Claude), so style and mistakes are less varied than real students'. Inter-rater agreement (is the rubric clear?) is still valid; engine-vs-human agreement is indicative, and P1.7 should add ≥ 15 real sessions before final weights.
- Ciel's replies, the planted bug, the judges' verdicts and the engine scores are real outputs of production, not simulated.
- Claude also wrote the scoring engine. To avoid designing sessions around engine features, profiles are defined from the **human rating guide** levels, and Claude does not rate.

## Design of the 40 sessions

- **Students:** 20 simulated accounts × 2 sessions (the export caps 3 per user). Emails `calib.sim01@example.com` … `calib.sim20@example.com` (reserved domain, never delivered), names `Sim 01` …; random passwords kept in the private state file.
- **Exercises:** ~22 distinct exercises; 26 implement / 14 debug; 16 fresher / 14 junior / 10 senior; ≥ 10 sessions on exercises with the Ciel trap (`verification_trap`).
- **Language:** mostly Vietnamese (hypotheses, prompts, answers), ~8 in English, as in the class.
- **Duration:** 6–30 real minutes, all 40 run concurrently (≈ 35 minutes wall time).
- **Code states** come from the reviewed content: untouched starter, reference solution, mutants (one-line bugs) and a few hand-written partial or off-topic attempts. Mutants are profiled first (Task 3) so "visible tests pass, hidden fail" sessions use a mutant that really behaves that way.
- **Target spread** (intended levels per the rating guide; realised levels are re-checked after the run because Ciel is live):

| Axis | 0 | 1 | 2 | 3 | N/A |
|---|---|---|---|---|---|
| Understanding | 8 | 10 | 12 | 10 | — |
| Hypothesis | 10 | 10 | 10 | 10 | — |
| Prompting | 6 | 8 | 8 | 6 | 12 (no Ciel) |
| Verification | ~5 | ~5 | ~5 | ~5 | rest (no AI code) |
| Testing | 8 | 8 | 12 | 12 | — |
| Debugging | 6 | 7 | 8 | 7 | ~12 (implement, never failed) |

  Overall: ~10 Emerging, ~12 Developing, ~12 Strong, ~6 Exceptional. Plus 6 sessions with integrity signals (tab hidden / window blur, one heavy) and 2 odd sessions (nearly empty; code unrelated to the task) that the guide tells raters to rate and annotate.
- **Mixed profiles on purpose** (not all-good / all-bad): e.g. correct code with a wrong explanation; strong hypothesis then blind AI-code acceptance; many trial-and-error runs that end fully passing; a good prompter who never runs tests.

## Private files (not in git until rating is finished)

`D:/FPT_University/Ki_7/EXE101/Product/calibration-private/` (sibling of the repos):
`scripts/sim-01.json` … `sim-40.json`, `state.json` (accounts, attempt ids, questions), `answers.json`, `profiles.json` (intended levels). After the team finishes rating they are committed under `docs/calibration/sim/` with the results.

---

### Task 1: Export filters and private id map

`app/features/calibration/export.py`:
- `build_sessions(..., email_like: str | None = None)`: when given, only attempts of users whose email matches (SQL `LIKE`).
- `duration_min` = minutes from start to the `SUBMIT` event (fallback: last event), so a late explain-back does not inflate it.
- Return a third value `keys: {sid: attempt_id}`; CLI `--keys-out FILE` writes it (private, like `engine.json`); CLI `--email-like PATTERN`.

Tests (`tests/test_calibration_export.py`): the filter keeps only matching users; duration stops at SUBMIT; keys map every sid to its attempt and are absent from `sessions.json`. Commit `feat(calibration): filter export by account and write a private id map`.

### Task 2: Session script schema

`app/features/calibration/simulate.py` (pydantic models):
- `Step`: `at` (minutes from open), `do` ∈ `hypothesis | code | run | ask | use_ai_code | away | submit`, with `text` (hypothesis / prompt), `ref` (`starter | reference | mutant:N | inline`), `code` (for inline), `send_code` (attach the editor code to a Ciel message), `seconds` (for `away`), `kind` (`tab` | `window`).
- `Script`: `id`, `student` (1–20), `exercise`, `locale` (`vi` | `en`), `steps` (sorted by `at`, must end with `submit`).
- `resolve_code(ref, exercise_content)`: starter via `student_starter`, reference, mutant N (1-based), inline.

Tests: invalid scripts are rejected (no submit, unknown ref, mutant index out of range); refs resolve to the content file's code. Commit `feat(calibration): add simulator script schema`.

### Task 3: Mutant profile

`python -m app.features.calibration.simulate profile-mutants`: runs every exercise's mutants through the local sandbox against visible and hidden tests and prints, per mutant, visible pass/total and hidden pass/total. Used when authoring scripts (Task 5). Test: a tiny fake exercise where one mutant passes visible and fails hidden. Commit `feat(calibration): profile mutants by visible and hidden results`.

### Task 4: Simulator runner (phase 1 and phase 2)

`simulate.py` runner, mirroring `codeprove-web` (`lib/api.ts`, `SolveWorkspace.tsx`):
- Sign up (or log in if the account exists), `POST /api/attempts`, client `OPEN` event.
- `hypothesis` → `POST /hypothesis`; `code` → client `CODE_EDIT {charsAdded}` + `POST /snapshots` (version kept in step with `/run`'s own snapshots so the latest snapshot is the editor code); `run` → `POST /run {run_tests: true}`; `ask` → `POST /mentor {message, code?}`; `use_ai_code` → takes the largest code block of the last Ciel reply if it defines the exercise's entry function, else keeps the current code (logged either way); `away` → `TAB_HIDDEN`/`TAB_VISIBLE` or `WINDOW_BLUR`/`WINDOW_FOCUS` events with their integrity flags; `submit` → `POST /submit?locale=…`, store the questions.
- Real-time pacing (`--speed`, default 1.0), all scripts concurrent (`asyncio.gather`), per-script log of every call and reply to `calibration-private/logs/`, resumable `state.json` (a finished step is never replayed; a failed script can be re-run from scratch with a fresh attempt).
- Phase 2: `answer` command posts `answers.json` to `/explain-back` and records the returned overall/tier.
- CLI: `python -m app.features.calibration.simulate run --api URL --scripts DIR --state FILE [--only sim-07] [--speed 1]` and `answer --api URL --state FILE --answers FILE`.

Tests (MockTransport, speed ∞): call order and payloads for a script; the snapshot version logic; `use_ai_code` keeps code when the reply has no matching function; phase 2 posts the saved questions with the answers. Commit `feat(calibration): add the session simulator`.

### Task 5: Author the 40 scripts (private)

Claude writes `scripts/sim-01..40.json` and `profiles.json` to the design above, checks the spread table by script, and dry-runs every script offline (MockTransport) for validity. Not committed until rating ends.

### Task 6: Run on production

1. Smoke: `--only sim-01`, then check the attempt via `GET /report` and the logs; fix anything odd.
2. Phase 1: all 40 concurrently (~35 min).
3. Claude writes `answers.json` from each session's questions, final code and profile (answer quality per the intended Understanding level).
4. Phase 2: post answers; all 40 attempts must be `scored`.
5. Re-check realised behaviour from the logs (e.g. Ciel gave no code → Verification is N/A) and correct `profiles.json` to what actually happened.

Cost: roughly 250–350 small LLM calls in total (Ciel, judges, question generation), on the existing `OPENAI_MODEL`.

### Task 7: Owner export and page seeding

Owner (after Tasks 1–4 are merged and deployed to EC2):
```
docker exec codeprove_backend python -m app.features.calibration.export --out /tmp/golden --email-like 'calib.sim%@example.com' --keys-out /tmp/golden/keys.json
docker cp codeprove_backend:/tmp/golden ./golden
```
and sends `sessions.json`, `engine.json`, `keys.json` (keep all three out of git and off the page).

Claude: checks there are 40 sessions and no leftovers of personal data, seeds `sessions/*` in one `ArtifactData` batch, and updates the page and `huong-dan-cham.md`: the sessions are simulated (played through the real system), step "do 5 exercises" removed.

### Task 8: Analysis CLI

`app/features/calibration/analyze.py` + `python -m app.features.calibration.analyze --data DIR --out FILE.md`, where DIR holds the `ArtifactData` dumps (`ahp/`, `ratings/<rater>/items/`), `engine.json`, `keys.json`, `profiles.json`:
- AHP: each member's weights and CR (flag ≥ 0.1), group weights by AIJ (`ahp.aggregate`), side by side with the current engine weights and equal weights.
- Inter-rater: ICC(2,1)/(2,k) on the overall level (Emerging..Exceptional = 0..3); per axis mean pairwise quadratic κ and N/A agreement; axes with κ < 0.6 flagged as "rubric unclear".
- Engine vs humans: Spearman per axis (engine score vs mean human level, sessions where the majority did not say N/A) and overall; N/A agreement between engine and majority.
- Intended profile vs humans (sanity check only).
- Uses only the rows present: works with 2–4 raters and partial ratings, and says how many are missing.

Tests with small synthetic dumps (known answers). Commit `feat(calibration): add golden-set analysis report`.

### Task 9: Results (after the team finishes)

Claude pulls `ahp` and `ratings` with `ArtifactData` (`out_dir`), runs Task 8 and writes `docs/calibration/results-<date>.md` with the limitations above; commits the private scripts/profiles under `docs/calibration/sim/`. Then P1.4 starts (roadmap order).

### Task 10: Cleanup (after P1.7)

A script removes the 20 simulated accounts and their attempts from production once P1.7 no longer needs them, so they stop affecting acceptance rates and dashboards. Until then they are identifiable by the `calib.sim%@example.com` emails.

## Who does what

| Step | Who | When |
|---|---|---|
| Tasks 1–5, smoke run | Claude | now |
| Merge PR, deploy to EC2 (`git pull` + rebuild) | Kiệt | after Tasks 1–4 |
| Tasks 6.2–6.5 (full run, answers) | Claude | after deploy (the simulator only needs the API, but the export needs Task 1 on EC2) |
| Export + send 3 files | Kiệt | after Task 6 |
| AHP form (15 pairs, alone) | 4 members | any time, already open |
| Rate 40 sessions (alone) | 4 members | after seeding, 3–4 h in several sittings |
| Task 8 now, Task 9 after rating | Claude | — |
