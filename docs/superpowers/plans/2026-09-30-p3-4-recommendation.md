# P3.4 Next-Exercise Recommendation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Suggest the next exercises from the learner model (P3.3): unsolved exercises that practise the student's weakest skills, with a predicted success chance near 70%. The suggestions are used on the Feedback page (same `candidates` interface as P1.5) and on the Dashboard.

**Architecture:**
- One deterministic ranking function in `app/features/learner/recommend.py`, with no LLM call.
- `feedback/next_exercise.candidates` keeps its signature and delegates to it, so the writer, templates and "try next" link keep working unchanged.
- The dashboard gets a new `recommended` field.
- No migration, no data change.

**Tech Stack:** SQLAlchemy async, FastAPI, pytest.

---

## Ranking (for approval)

For each unsolved exercise E (never scored by the student, not the current one):

- `p` = Elo expected result of the student against E: `expected(mean rating over E's tags, difficulty(E))`. An unrated tag counts as 1000.
- `weak` = number of E's tags among the student's 2 weakest **rated** skills (≥ 2 attempts, the same rule as the brief). Its value is 0–2.
- Lower score is better:
  `score = |p − 0.70| − 0.10·weak − 0.10·[debugging risk in this report and E is a debug exercise] + 0.30·[an unfinished attempt on E started < 24 h ago]`
- Ties are broken by exercise code. The top 3 are returned.

What this gives:

| Case | Result |
|---|---|
| New student | Fresher exercises first (p ≈ 0.64), then junior (p ≈ 0.36), then senior (p ≈ 0.15). |
| Strong student (hash-map rated 1250) | Junior hash-map exercises (p ≈ 0.70). |
| After a debugging risk | Debug exercises get the same small push as in P1.5. |

## Decisions to approve

1. **The formula above:** target 0.70, weights 0.10 / 0.10 / 0.30, recency window 24 h.
2. **Level window on the Feedback page:** keep P1.5's rule (same level as the exercise just done, or one above), ranked by the formula inside it. Without it, a student who just finished a senior exercise would be sent back to fresher ones. The Dashboard has no current exercise, so it ranks every unsolved exercise.
3. **Fresh ratings:** at scoring, update the learner model *before* building the feedback. The suggestion then reflects the attempt just scored. Today the update runs after it. It stays wrapped: an error is logged and scoring continues.
4. **Dashboard card:** add `recommended` (3 items) to `GET /api/dashboard`. A "Bài nên làm tiếp" card is handed to CodeProve-UI via spawn_task. Each item shows the title, level, skills and a short reason, e.g. "luyện Đồng thời, đa luồng". The success percentage is not shown to students.

---

### Task 1: Ranking

**Files:**
- Create: `app/features/learner/recommend.py`
  - `TARGET = 0.70`, the weights, `RECENT_HOURS = 24`, `LIMIT = 3`.
  - `rank(pool, ratings, weak, wants_debug, recent_ids)` is pure. It returns `[Recommendation(code, title, level, kind, skills, p, weak_skills)]`.
  - `recommend(db, user_id, *, current=None, levels=None, wants_debug=False, limit=LIMIT)`. It loads unsolved exercises (optionally within `levels`, never `current`), the student's `learner_skills`, and their unfinished recent attempts. It then calls `rank`.
- Test: `tests/test_learner_recommend.py`
  - the three cases in the table;
  - solved and current exercises are excluded;
  - a weak skill wins at equal p;
  - the debug push;
  - a recent unfinished attempt goes last;
  - untagged exercises still rank by level difficulty;
  - deterministic ties.

### Task 2: Feedback uses it

**Files:**
- Modify: `app/features/feedback/next_exercise.py`: `candidates()` keeps its signature and returns `[r.code for r in await recommend(db, user_id, current=exercise, levels=<same or one above>, wants_debug=<P1.5 risks>)]`.
- Modify: `app/features/attempts/scoring_service.py`: call `record_attempt` right after the result is computed and before `build_diagnosis` (still in try/except).
- Test:
  - Update `tests/test_feedback_next_exercise.py`. The level window, solved-skip and debug-first tests stay. "Same category first" becomes "weak skill first".
  - Add a flow test: the report's `diagnosis.candidates` reflects the ratings including the attempt just scored.

### Task 3: Dashboard

**Files:**
- Modify: `app/features/dashboard/service.py` and `app/schemas/dashboard.py`: `recommended: [{code, title, level, kind, skills: [{key, vi, en}], reason_skills: [keys]}]`. `reason_skills` = the weak skills E practises, possibly empty. `p` is not exposed.
- Modify: `docs/api/learner.md`: add a "Recommendations" section with the dashboard field and the ranking in words.
- Test: dashboard returns 3 recommendations for a new user (fresher first) and none of the solved ones.

### Task 4: Frontend handoff (CodeProve-UI)

- One spawn_task chip: a Dashboard "Bài nên làm tiếp" card from `recommended`. Each item has title, level badge, skill labels, and "Luyện: <reason skills>" when present. It links to the exercise. If the list is empty, the card is hidden. The card reads its labels from the API in the current locale.

### Task 5: Ship (Kiệt)

No migration, no data step. Deploy on EC2:

```bash
cd ~/CodeProve-Backend && git pull origin main && docker compose up -d --build
```

Then open the Dashboard and score one attempt to see the new suggestions.

**Out of scope:**
- Showing the success chance to students.
- Collaborative filtering or anything learned.
- Re-suggesting solved exercises for review.
- A rescore (`refresh_diagnosis`) also uses the current ratings, so old reports may get new suggestions after a rescore. This is accepted: suggestions are advice, not part of the score.
