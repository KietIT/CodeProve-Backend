# P3.6 Cost Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:**
- Cap what one student can spend on LLM calls.
- Lay Ciel's prompt out so OpenAI's automatic prompt caching can apply.
- Know what the LLM costs each month.

**Architecture:**
- **Quotas** are counted from the database (`prompt_logs`), so they survive restarts and work with several workers. A short in-memory burst limit (the existing `core/rate_limit`) stops rapid-fire spam.
- **Ciel's messages** are reordered so that the long part repeated on every turn comes first: system text, exercise, learner brief, hint style, then the attempt's history. What changes every turn comes last: the student's code, one-off instructions, the new question.
- **Logging:** every LLM call (Ciel and all judges) is logged to a new `llm_calls` table.
- **Report:** a monthly report script reads that table.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest. No new dependency.

**Found while planning:** `POST /api/attempts/{id}/mentor` and `/hypothesis` have **no limit at all** today, not even per minute. One account can trigger unlimited LLM calls.

---

## Decisions to approve

1. **Quota numbers** (all in `.env`, changeable without code):
   - Ciel: **30 messages per attempt**, **100 per student per day** (Vietnam calendar day), and **10 per minute** against spamming.
   - Hypothesis checks: **10 per attempt**.
   - A guard retry (P2.1/P2.2) does not count: one student message counts as one.
   - When a limit is reached, the API returns 429 with `{code: "ciel_attempt_limit" | "ciel_daily_limit" | "rate_limited", message_vi, message_en}`. Scoring is not affected.
2. **Show the remaining count.** The mentor reply and the attempt state carry `ciel: {attempt_left, day_left}`. The frontend shows "Còn N tin nhắn với Ciel" when N ≤ 10, the limit message when N = 0, and disables the input. This is handed to CodeProve-UI.
3. **Ciel prompt layout for caching.**
   - New message order: `[system: rules + exercise + learner brief + hint style]`, `history…`, `[system: this turn's instructions: debug locate rule / injected-error trap / guard retry]`, `[user: question + current code]`.
   - The student's code moves from the system prompt into the last user message. Today it is inside the system prompt, so the prefix changes on every turn and nothing can be cached.
   - OpenAI only caches prompts of 1024+ tokens. A first question is usually shorter, so the gain shows from about the 3rd–4th turn of an attempt.
   - The cached token count is logged, so the effect can be measured.
   - Because the prompt order changes, the P3.5 check sheet should be rerun after deploy.
4. **Log every LLM call; no model tiering.**
   - The `llm_calls` table holds kind, model, input/cached/output tokens, user and attempt ids, and time. It never holds message text.
   - Model tiering is skipped: everything already runs on `gpt-4o-mini`, the small model.
   - Prices per million tokens go in `.env`. **Kiệt checks them on OpenAI's pricing page before relying on the report.** The defaults in code are marked as "verify".

---

### Task 1: Quotas

**Files:**
- Modify `app/core/config.py`:
  - `ciel_per_attempt=30`, `ciel_per_day=100`, `ciel_per_minute=10`, `hypothesis_per_attempt=10`;
  - `quota_timezone="Asia/Ho_Chi_Minh"`.
- Create `app/features/mentor/quota.py`:
  - `ciel_left(db, user_id, attempt_id) -> {attempt_left, day_left}` counts `PromptLog` rows: this attempt's rows, and the user's rows since local midnight;
  - `enforce_ciel(db, user, attempt)` applies the minute burst first, then the two counts, and raises 429 with the bilingual detail;
  - `enforce_hypothesis(db, attempt)` counts the `HYPOTHESIS` events of the attempt.
- Modify `app/features/mentor/router.py`: enforce before calling the service, and add `ciel` to `MentorOut`.
- Modify `app/features/attempts/router.py` and its schema: `AttemptState.ciel`.
- Tests `tests/test_mentor_quota.py`:
  - the 31st message of an attempt → 429 `ciel_attempt_limit`;
  - the 101st of the day across attempts → `ciel_daily_limit`;
  - yesterday's messages do not count (VN midnight);
  - the burst limit;
  - a guard retry counts once;
  - the hypothesis limit;
  - `ciel` counts in the reply and in the state;
  - other users are not affected.

### Task 2: Prompt layout for caching

**Files:**
- Modify `app/features/mentor/client.py`:
  - `chat(...)` builds `[system static, *history, system turn (if any), user]`;
  - it takes `code` and appends it to the user message as a fenced block;
  - it returns `cached_tokens` from `usage.prompt_tokens_details`.
- Modify `app/features/mentor/service.py`:
  - static context = exercise + learner brief + hint style, without the student's code;
  - turn instructions = injected trap, locate rule, retry;
  - `cachedTokens` goes into the AI_REPLY payload.
- Modify `app/features/mentor/prompts.py` and `service.build_exercise_context`: drop the student-code part (it moves to the user message).
- Tests:
  - message order with and without history;
  - the static system text is identical across two turns of one attempt, even when the code changes;
  - the code is in the last user message;
  - the turn instructions sit after the history;
  - all P2.1/P2.2/P3.1/P3.5 tests still pass;
  - `cachedTokens` is recorded.

### Task 3: Log every LLM call

**Files:**
- Create `app/models/llm_call.py`: `LlmCall(id, kind str(24), model, prompt_tokens, cached_tokens, completion_tokens, user_id null FK set-null, attempt_id null FK set-null, created_at)` with an index on `created_at`.
- Create migration `c5e7a9b1d3f6_llm_calls.py`, revising the current head.
- Modify `app/features/mentor/client.py`:
  - `chat` and `judge` take `kind` (`ciel`, `ciel_retry`, `explain_questions`, `explain`, `hypothesis`, `prompts`, `locate`, `feedback`, `daily`) and optional `user_id` / `attempt_id`;
  - they return usage, and the caller logs it with `record_call(db, ...)`;
  - a logging failure never breaks the call.
- Update the callers listed in `grep get_mentor_client`: mentor service, scoring_service, judges, feedback writer, daily content. Rescore backfill and preview are logged as `kind="offline"`.
- Tests:
  - one Ciel message logs 1 row, or 2 with a guard retry;
  - explain-back logs its judge calls;
  - no text is stored;
  - a DB error in logging does not fail the request.

### Task 4: Monthly cost report

**Files:**
- Create `app/features/mentor/cost_report.py`: `python -m app.features.mentor.cost_report --month 2026-10`. It prints, per kind and in total:
  - calls, input, cached and output tokens;
  - estimated USD from `.env` prices (`OPENAI_PRICE_INPUT_PER_M`, `..._CACHED_PER_M`, `..._OUTPUT_PER_M`);
  - Ciel messages per active student (mean, max);
  - how many students hit a limit.
  It shows ids only, never names or emails.
- Tests: totals and the price maths on seeded rows; an empty month.

### Task 5: Frontend handoff (CodeProve-UI)

- One spawn_task chip, for the Ciel panel:
  - read `ciel.attempt_left` / `day_left` from the attempt state and each reply;
  - show "Còn N tin nhắn với Ciel" when N ≤ 10;
  - on 429, show `message_vi` / `message_en` and disable the input.

### Task 6: Ship (Kiệt)

There is a migration, which runs on container start. On EC2:

```bash
cd ~/CodeProve-Backend && git pull origin main && docker compose up -d --build
```

Add the prices to `.env` on EC2 (values from OpenAI's pricing page), then restart with the same command. After some days of use:

```bash
docker exec codeprove_backend python -m app.features.mentor.cost_report --month 2026-10
```

Then rerun the P3.5 Ciel check sheet (the prompt order changed).

**Out of scope:**
- Paid tiers and per-plan quotas.
- Redis for the burst limiter (still in-memory, one worker).
- Model tiering.
- Alerts.
