# P1.3 AHP Weights and Golden Set Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the axis weights and the scoring engine an evidence base: the 4-member team derives weights with AHP, and rates ~40 anonymised real sessions (the golden set) so we can measure human-human and engine-human agreement.

**Architecture:** Pure-Python calibration modules in the backend (AHP maths, agreement statistics, anonymised export). A private claude.ai web page (Artifact with `db` + `user` capabilities) hosts the team guide (Vietnamese), the AHP form and the rating form; results live in the page's shared database, which Claude reads with `ArtifactData` for analysis. No numpy/scipy (not in requirements): the maths is small.

**Tech Stack:** FastAPI/SQLAlchemy (export), pure Python (maths), Artifact page (HTML/JS) with `db` and `user`.

**Design:** `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.3), roadmap section "Axis weights". Owner decisions (2026-09-24): web page with forms; classmates are invited to generate sessions.

---

## Roadmap traceability

| Item | Task |
|---|---|
| [2] Axis weights v1 via AHP (3–5 experts, CR < 0.1), benchmarked against equal weights | 2, 6, 7 |
| [2] Start a golden set of 30–50 human-rated sessions | 1, 3, 4, 5, 6, 7 |
| Team members who do not talk to Claude must understand what to do and why | 5, 6 |

## Prerequisites (owner)

1. P1.2 merged and deployed (sessions then carry the full-suite result at submit).
2. Task 1 deployed **before** classmates start: hypothesis text is not stored today.
3. Trung, Minh and Phát each have a claude.ai account; the owner shares the page with them with at least "can interact" access (only signed-in, invited viewers can write to the page's database).

## Who does what, when

| Step | Who | Effort | When |
|---|---|---|---|
| AHP form (15 pairwise questions, alone) | 4 members | 20–30 min | As soon as the page is shared |
| Do 5 exercises seriously, varied behaviour | 4 members | ~2 h | Week 1 |
| Invite 10–20 classmates (message + consent in Task 5) | Kiệt | — | Week 1 |
| Export sessions on EC2, send the files to Claude | Kiệt | 15 min | When ≥ 40 good sessions exist |
| Rate the ~40 sessions (alone, no discussion until done) | 4 members | 3–4 h, several sittings | Week 2 |
| Analysis + results report | Claude | — | After rating |

---

### Task 1: Store the hypothesis text

`app/features/mentor/service.py` `judge_hypothesis`: the `HYPOTHESIS` event payload becomes `{"proposedBy": "user", "correct": correct, "text": text[:2000], "note": verdict note}`. Test in `tests/test_mentor.py`: the event keeps the text. Commit `feat(mentor): keep the hypothesis text in the event`.

### Task 2: AHP maths

`app/features/calibration/ahp.py` (pure functions):
- `AXES` (6 axis keys), `PAIRS` (the 15 ordered pairs), Saaty random index `RI` (n=6 → 1.24).
- `matrix(answers)`: `answers[(a, b)]` on Saaty's scale (1..9 if a wins, 1/9..1 if b wins) → reciprocal matrix; rejects out-of-range values and missing pairs.
- `priorities(m)`: principal eigenvector by power iteration, normalised to sum 1.
- `consistency_ratio(m)`: `((λmax − n)/(n − 1)) / RI[n]`.
- `aggregate(ms)`: element-wise geometric mean of individual matrices (AIJ).
- `worst_pairs(m, k=3)`: pairs deviating most from `w_i / w_j`, shown to a respondent whose CR ≥ 0.1.

Tests: a matrix built from known weights (e.g. 0.3/0.25/0.15/0.15/0.1/0.05) returns those weights and CR ≈ 0; a deliberately intransitive matrix gets CR > 0.1 and its planted pair is first in `worst_pairs`; aggregating identical matrices returns the same matrix. Commit `feat(calibration): add AHP weights and consistency ratio`.

### Task 3: Agreement statistics

`app/features/calibration/agreement.py`:
- `icc2(x)`: ICC(2,1) and ICC(2,k) (two-way random, absolute agreement; Shrout & Fleiss 1979) for a subjects × raters matrix.
- `quadratic_kappa(a, b, categories=4)` and `mean_pairwise_kappa(ratings)`: per axis over levels 0–3; pairs where either rater said N/A are dropped, and N/A agreement is reported separately.
- `spearman(x, y)` with average ranks for ties: engine score vs the mean human level.

Tests: the Shrout & Fleiss example (6 subjects × 4 judges, rows 9 2 5 8 / 6 1 3 2 / 8 4 6 8 / 7 1 2 6 / 10 5 6 9 / 6 2 4 7) gives ICC(2,1) = 0.29 and ICC(2,4) = 0.62; identical ratings give κ = 1; fully reversed binary ratings give κ = −1; `spearman([1,2,3,4],[1,3,2,4]) == 0.8`. Commit `feat(calibration): add agreement statistics`.

### Task 4: Anonymised golden-set export

`app/features/calibration/export.py` + CLI `python -m app.features.calibration.export --out DIR [--limit 60]`:
- Selects scored attempts with a code snapshot and explain-back answers, newest first, at most 3 per user (diversity).
- Session id `S` + 8 hex chars of `sha256(random_salt + attempt_id)`; the salt is never stored, so ids cannot be linked back to users.
- Per session: exercise (code, title, kind, level, summary), duration, hypotheses (text, verdict, minute), prompts to Ciel with replies (from `prompt_logs`, flagged when the reply carried the planted bug), runs (minute, pass ratio, untouched-starter flag), submit-suite summary, final code, explain-back Q&A, integrity counts. No user id, name, email or timestamps.
- Free text is scrubbed of email addresses and phone numbers.
- Writes `sessions.json` (for the page) and `engine.json` (engine axes + overall per session id, kept off the page so raters are not anchored).

Tests (sqlite): output has no user fields, emails in prompts are replaced, ids are stable within one export and opaque, per-user cap applied, engine scores only in `engine.json`. Commit `feat(calibration): add anonymised golden-set export`.

### Task 5: Team documents (Vietnamese)

- `docs/calibration/huong-dan-cham.md`: the rating guide. For each axis, levels 0–3 (or "không áp dụng") with a description and one worked example; overall level (Emerging / Developing / Strong / Exceptional); rules: rate alone, do not look at others' ratings, rate what the session shows, not what you think the person knows.
- `docs/calibration/moi-ban-cung-lop.md`: the invitation message for classmates and the consent text (their anonymised code, prompts and answers will be read by the 4 team members for research on the scoring; they may opt out by telling Kiệt).

Draft levels (finalised with the team before rating; they seed the P1.4 rubric):

| Axis | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Understanding | no/irrelevant/wrong explanation | vague or partly wrong | correct but only *what*, not *why* | correct and explains *why* (reasoning, edge cases) |
| Hypothesis | none | vague ("use a loop") | correct approach | correct approach + an edge case or complexity, before coding |
| Prompting (N/A without Ciel) | asks for the full answer / off-topic | short, vague ("fix it") | specific question with context | specific, says what was tried/failed, asks for guidance not answers |
| Verification (N/A without AI code) | kept AI code blindly (planted bug survived) | used AI code with little checking | ran tests after AI code | spotted/fixed the AI's bug or questioned the suggestion |
| Testing | never ran / submitted failing | ran but ignored failures | visible pass, some hidden fail | whole suite passes |
| Debugging (N/A: implement, never failed) | never fixed | fixed by trial and error | fixed after a few focused attempts | located and fixed quickly with clear reasoning |

Commit `docs(calibration): add rating guide and classmate invitation`.

### Task 6: Calibration web page

Built with the Artifact tool (quickstart first, then the `artifact-design` skill; capabilities `db` + `user`). Vietnamese UI. Sections:

1. **Giới thiệu**: why the team is doing this, what each person does, time needed, deadlines, privacy.
2. **AHP**: 15 pairwise questions (A ⟷ B on a 17-step slider from "B tuyệt đối" through "ngang nhau" to "A tuyệt đối"), live CR computed in the page (same maths as Task 2); when CR ≥ 0.1 it highlights the 3 most inconsistent pairs; saving writes `ahp/<viewer id>`.
3. **Chấm bộ mẫu**: the session list (seeded by Claude into `sessions/*`), a session view (exercise, timeline of hypotheses / prompts / runs, final code, submit result, explain-back), and the rating form (6 axes × {0,1,2,3,N/A} with the descriptors inline, overall level, optional note). Progress per rater; ratings write `ratings/<viewer id>__<session id>`. A rater only sees their own ratings in the UI.
4. **Hướng dẫn chấm**: the Task 5 guide.

Database rules: `sessions` admin-only writes (Claude seeds with `ArtifactData`), `ahp` and `ratings` writable by interacting viewers. After the first publish: one `ArtifactData` list of each collection, and a read as an interact-level viewer to confirm `sessions` cannot be written by them.

### Task 7: Seed, collect, analyse

1. Kiệt runs the export on EC2 (`docker exec codeprove_backend python -m app.features.calibration.export --out /tmp/golden`, then `docker cp`) and sends `sessions.json` + `engine.json`.
2. Claude checks the sessions (≥ 40 with real work; a spot check for leftover personal data) and seeds `sessions/*` with one `ArtifactData` batch.
3. After everyone has saved AHP and finished rating: Claude reads `ahp` and `ratings`, runs Tasks 2–3 locally and writes `docs/calibration/results-<date>.md`: each member's CR, group weights vs the current weights vs equal weights, inter-rater ICC/κ per axis (flagging axes below 0.6 as unclear rubric), engine-vs-human Spearman per axis. The P1.4/P1.7 decisions start from this report.
