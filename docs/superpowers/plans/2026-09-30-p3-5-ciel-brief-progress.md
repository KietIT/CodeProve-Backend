# P3.5 Ciel with the Learner Brief, Scaffolded Hints, Progress Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:**
- Ciel knows what the student is good and weak at, from the learner brief (P3.3).
- Ciel adapts how concrete its hints are.
- The student gets a progress page built from the learner model.

**Architecture:**
- **Mentor:** `mentor_reply` adds two blocks to Ciel's system prompt, after the exercise context:
  - the learner brief (English, deterministic, no PII);
  - a hint-style instruction.
  The P2.1/P2.2 guards and the P3.1 attempt memory run unchanged.
- **API:** `GET /api/learner/me` gains what the progress page needs:
  - the student's recent report history;
  - the reviewed practice phrase of each recurring issue.
- **Frontend:** the page is handed to CodeProve-UI.
- No migration, no LLM call added (the brief is built from data; no LLM summary).

**Tech Stack:** FastAPI, SQLAlchemy async, pytest. No new dependency.

---

## Decisions to approve

1. **The brief in Ciel's context.**
   - The English brief goes in a block marked "use silently to adapt your help". Ciel never quotes ratings, never tells the student they are weak at something, and never mentions the block.
   - The block is left out while the student has no scored exercise.
   - An opt-out of personalisation comes with P3.7 (privacy); until then every student gets it.
2. **What sets the hint style.** Recommended: **(A) the exercise level**. Everyone on the same exercise gets the same kind of help, so scores stay comparable, which matters on an assessment platform.
   - Alternative **(B)**: the student's predicted success on this exercise (Elo p). This is more personal, but two students on the same exercise would get different help.
   - With (A):
     - **fresher:** Ciel may name the concept or data structure to use and show a tiny generic snippet (≤ 5 lines) of one building block.
     - **junior:** the current behaviour (guiding questions and pointers).
     - **senior:** Socratic questions only. Ciel shows code only after the student has explicitly asked for code twice in this attempt, and then only a small fragment.
   - The guards still withhold any reply that solves the exercise or reveals the bug location.
3. **The progress page** shows each skill as a bar plus a word ("tốt" / "trung bình" / "cần luyện"), never the raw Elo number.
   - Skills with fewer than 2 attempts appear as "chưa đủ dữ liệu".
   - Each axis gets a trend over the last 10 scored exercises.
   - Recurring issues are shown with the team-reviewed practice phrases.
   - The page also shows the Dashboard's recommended exercises.
   - There is no LLM-written summary: that would add cost, risk leaking content, and need a new review.
4. **Check before release.** Ciel's replies cannot be unit-tested for quality, so the team runs a short manual check after deploy with the sheet `docs/calibration/ciel-p35-kiem-tra.md`. It covers 3 exercises (fresher, junior, senior) × 2 students (new, and one with a weak skill). The sheet lists what to ask and what to look for.

---

### Task 1: Learner brief in Ciel's context

**Files:**
- Modify `app/features/mentor/prompts.py`: add `LEARNER_BLOCK`, a header plus rules: use it silently; never state ratings or call the student weak; never mention it; it must not change the no-solution rules.
- Modify `app/features/mentor/service.py`:
  - `learner_context(db, user_id) -> str` returns `""` when there is no scored attempt, else `LEARNER_BLOCK + learner_brief(profile, "en")`.
  - It is appended to `context` for both `client.chat` calls (the first try and the guard retry).
  - A failure to build it is logged and Ciel answers without it.
- Test `tests/test_mentor_learner_context.py`:
  - a new student gets no block;
  - a student with reports gets the brief;
  - the block reaches both the first call and the retry (fake client records `context`);
  - the brief has no email or name;
  - a profile error does not break the reply.

### Task 2: Hint style by exercise level (if decision 2 = A)

**Files:**
- Modify `app/features/mentor/prompts.py`: `HINT_STYLE = {"fresher": ..., "junior": "", "senior": ...}`.
- Modify `app/features/mentor/service.py`:
  - The style for `ex.level` is appended to `extra_instruction` for both calls.
  - On a debug exercise with the bug still hidden, the P2.2 `LOCATE_INSTRUCTION` wins: it comes last and says it overrides the hint style.
  - Senior's "asked for code twice" rule is counted from this attempt's `PromptLog` prompts with the existing `looks_like_priming` / code-request keywords, and passed as a flag.
- Test:
  - each level gets its instruction (junior none);
  - a debug exercise with a hidden bug still carries the locate rule last;
  - the senior flag flips after two code requests;
  - the guards still replace a solving reply at every level.

### Task 3: Progress data in `GET /api/learner/me`

**Files:**
- Modify `app/features/learner/profile.py`:
  - `history`: the last 10 scored reports, oldest first. Each item has `{date, code, title, overall, levels}`; `levels` is null for v1 reports.
  - Each `recurring` item gets `practice` in the request locale, from `feedback/templates.py`.
- Modify `app/features/learner/router.py` so the response carries these fields.
- Modify `docs/api/learner.md` with the new fields and a "Progress page" section: what to show, "tốt / trung bình / cần luyện" thresholds, the < 2 attempts rule, no raw numbers.
- Test:
  - history order and limit;
  - v1 reports have null levels;
  - the practice phrase follows the locale;
  - own data only.

### Task 4: Frontend handoff (CodeProve-UI)

- One spawn_task chip: a "Tiến độ" / "Progress" page (route and nav entry) from `GET /api/learner/me` and the dashboard's `recommended`. It has four sections:
  - skill bars with words;
  - axis trends;
  - recurring issues with practice phrases;
  - next exercises.
- Plus an empty state for a new student.

### Task 5: Check sheet and ship

- Write `docs/calibration/ciel-p35-kiem-tra.md`: 6 scenarios with the question to ask Ciel and the expected behaviour. Examples: fresher reply names the concept; senior reply only asks questions; no reply mentions ratings or "yếu"; no solution.
- Ship (Kiệt), no migration:

```bash
cd ~/CodeProve-Backend && git pull origin main && docker compose up -d --build
```

- Then the team runs the check sheet and reports back.

**Out of scope:**
- Any LLM summary.
- Opt-out and consent (P3.7).
- Quotas (P3.6).
- Changing the scoring of Ciel use.
