# P3.3 Learner Model and Learner Brief Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep an Elo rating per student per skill, plus an axis profile and recurring findings. Build a short, deterministic learner brief from them. The brief is what P3.4 (recommendation) and P3.5 (Ciel) will use.

**Architecture:**
- New feature package `app/features/learner/`:
  - `elo.py`: pure functions.
  - `service.py`: update after scoring, and the full rebuild.
  - `profile.py`: axis profile and recurring findings, read from recent reports.
  - `brief.py`: vi/en text.
  - `rebuild.py`: CLI.
  - `router.py`: `GET /api/learner/me`.
- Ratings are stored in a `learner_skills` table. Exercise difficulty goes in `exercises.difficulty_elo`.
- Everything is **recomputable**: `rebuild` replays every scored report in time order. It is run once at deploy (backfill) and again after any rescore.
- The profile and the brief are computed on read. Nothing extra is stored.

**Tech Stack:** SQLAlchemy async, Alembic, FastAPI, pytest. No new dependency, no LLM call.

---

## Decisions to approve

1. **Repeat attempts:**
   - Every scored attempt moves the student's skill ratings. The Elo expectation already rises as they improve, so redoing an easy exercise gains little.
   - The exercise's difficulty moves only on each student's *first* scored attempt of it. Otherwise a student repeating one exercise would make it look easier for everyone.
2. **Simulated calibration accounts** (`calib.sim*@example.com`) do not move exercise difficulty. Their quality levels were chosen by design, not by real students. Their own ratings are kept; they are harmless.
3. **Minimum evidence:** a skill is named strong/weak in the brief only after it has been practised on at least **2** scored attempts. The API still returns every rating, with its attempt count.
4. **Profile window:** the axis profile and recurring findings use the **last 5 scored v2 reports**. Old v1 reports have no levels; they still count for Elo, which uses only `overall`.

## Formulas (from the approved P3 design)

- Student rating R per skill: starts at 1000, K = 32.
- Exercise difficulty D: starts from level (fresher 900, junior 1100, senior 1300), K = 8.
- Outcome s = overall / 100, clamped to [0, 1]. It already includes the integrity multiplier.
- Expected E = 1 / (1 + 10^((D − R) / 400)).
- Per tagged skill: R += 32·(s − E).
- Difficulty uses the student's mean rating over the exercise's tags: D −= 8·(s − E_mean).
- An exercise with no approved tags updates nothing.

---

### Task 1: Elo core and storage

**Files:**
- Create `app/features/learner/__init__.py`.
- Create `app/features/learner/elo.py`: `START_RATING`, `LEVEL_DIFFICULTY`, `K_STUDENT`, `K_EXERCISE`, `expected(r, d)`, `outcome(overall)`, `update(ratings: dict[str, float], difficulty, overall, move_difficulty) -> (new_ratings, new_difficulty)`.
- Create `app/models/learner_skill.py`: `LearnerSkill(user_id FK cascade, skill str(40), rating float, attempts int, updated_at)` with unique `(user_id, skill)`. Register it in `app/models/__init__.py`.
- Modify `app/models/exercise.py`: `difficulty_elo: float | None` (None = not rated yet, use the level default).
- Create migration `b3d5f7a9c1e4_learner_model.py` (revises `a1c3e5f7b9d2`): the table plus the column.
- Test `tests/test_learner_elo.py`:
  - expected = 0.5 at equal ratings;
  - a win above expectation raises R and lowers D;
  - outcome is clamped;
  - multi-tag moves each tag;
  - `move_difficulty=False` leaves D unchanged.

### Task 2: Update after scoring + rebuild

**Files:**
- Create `app/features/learner/service.py`:
  - `record_attempt(db, attempt, exercise, overall)`: loads or creates the student's rows for the exercise tags, applies `elo.update`, and bumps `attempts`. It moves difficulty only when this is the student's first scored attempt of the exercise and the student is not a sim account.
  - `rebuild(db, apply)`: clears `learner_skills` and `difficulty_elo`, then replays every `FluencyReport` joined to its attempt, ordered by `(attempts.submitted_at, report.id)`. It returns a summary (reports replayed, students, skills).
- Modify `app/features/attempts/scoring_service.py`: call `record_attempt` in `score_with_explanations` before the commit. It is wrapped so that a learner-model error is logged and never fails scoring.
- Create `app/features/learner/rebuild.py`: `python -m app.features.learner.rebuild [--apply]`. A dry run prints the counts and the 5 exercises whose difficulty moved most.
- Tests `tests/test_learner_service.py`:
  - scoring an attempt creates ratings for its tags;
  - a second attempt of the same exercise moves the student but not the difficulty;
  - a sim account does not move difficulty;
  - an untagged exercise changes nothing;
  - rebuild equals the incremental result;
  - rebuild is idempotent.

### Task 3: Profile and learner brief

**Files:**
- Create `app/features/learner/profile.py`: `profile(db, user_id)` returns:
  - `skills`: [{key, vi, en, rating, attempts}] sorted by rating;
  - `axes`: mean level 0–3 per axis over the last 5 v2 reports, None when the axis was not applicable;
  - `recurring`: finding codes of kind risk seen in ≥ 2 of those reports, with counts;
  - `scored_attempts`.
- Create `app/features/learner/brief.py`: `learner_brief(profile, locale) -> str`, deterministic and at most about 300 tokens. Its lines are:
  - number of scored attempts;
  - up to 2 strongest and 2 weakest skills (≥ 2 attempts each; with the rating and a plain word: tốt / trung bình / cần luyện);
  - the weakest and the strongest axis;
  - up to 3 recurring issues phrased with the **team-reviewed `practice` phrase** of `feedback/templates.py`.
  - A student with no scored attempts gets one neutral line ("Chưa có bài nào được chấm.").
  - It never includes code, chat text, names or emails.
- Test `tests/test_learner_brief.py`:
  - empty profile;
  - a skill below the 2-attempt minimum is not named;
  - strong/weak ordering;
  - recurring issues use the template phrase;
  - vi and en;
  - a length cap;
  - no email or name appears.

### Task 4: API and docs

**Files:**
- Create `app/features/learner/router.py`: `GET /api/learner/me` returns `{skills, axes, recurring, scored_attempts, brief}` (brief in the request locale, default vi) for the current user only. Register it in `app/main.py`.
- Create `docs/api/learner.md`: the contract for the P3.5 progress page.
- Test: auth required; a user sees only their own data.

### Task 5: Ship (Kiệt)

1. Merge P3.1, P3.2 and P3.3.
2. Run `alembic upgrade head`.
3. Run `python -m app.features.content.sync --apply` to write the approved skill tags.
4. Run `python -m app.features.learner.rebuild` (dry run), check the counts, then add `--apply`.
5. Score one attempt and check `GET /api/learner/me`.

**Out of scope:**
- The recommendation (P3.4).
- Putting the brief into Ciel, and the progress page UI (P3.5). There is no frontend task in P3.3.
- Concurrent scoring of the same exercise may lose one difficulty update (last write wins). The next rebuild corrects it; accepted.
