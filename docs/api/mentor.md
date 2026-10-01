# Mentor API limits (P3.6)

Ciel and the hypothesis check call an LLM, so each student has caps. All numbers are backend `.env` settings; the UI must not hardcode them.

| Setting | Default | Applies to |
|---|---|---|
| `CIEL_PER_ATTEMPT` | 30 | Ciel messages in one attempt |
| `CIEL_PER_DAY` | 100 | Ciel messages per student per day (`QUOTA_TIMEZONE`, default Asia/Ho_Chi_Minh) |
| `CIEL_PER_MINUTE` | 10 | Ciel messages per student per minute (in-memory burst limit) |
| `HYPOTHESIS_PER_ATTEMPT` | 10 | Hypothesis checks in one attempt |

One student message counts once, even when the guard (P2.1/P2.2) had to ask the LLM again.

## `POST /api/attempts/{id}/mentor`

- **Body:** `{"message": str (1–4000 chars), "code": str | null (≤ 8000)}`.
- **Response:** `{"reply": str, "ciel": {"attempt_left": int, "day_left": int}}`. The counts are after this message.

## `POST /api/attempts/{id}/hypothesis`

- **Body:** `{"text": str (1–2000 chars)}`.

## `GET /api/attempts/{id}`

- Also returns `ciel: {attempt_left, day_left}`, so the UI can show the count before the first message.

## When a limit is reached

The response is HTTP 429, and the LLM is not called:

```json
{"detail": {"code": "ciel_attempt_limit", "message_vi": "Bạn đã dùng hết 30 tin nhắn với Ciel cho lượt làm bài này.",
            "message_en": "You have used all 30 Ciel messages for this attempt."}}
```

`code` is one of `ciel_attempt_limit`, `ciel_daily_limit`, `hypothesis_limit`, `rate_limited`. `rate_limited` also sends a `Retry-After` header (seconds). Show the message in the current locale. For the two Ciel limits, disable the input. For `rate_limited`, re-enable it after `Retry-After`.

## Cost logging

Every LLM call (Ciel, every judge, the feedback writer, daily generation) adds a row to `llm_calls`. A row holds the kind, model, token counts, user and attempt ids, and time; never text.

Monthly report on EC2:

```bash
docker exec codeprove_backend python -m app.features.mentor.cost_report --month 2026-10
```

Costs appear only when `OPENAI_PRICE_INPUT_PER_M`, `OPENAI_PRICE_CACHED_PER_M` and `OPENAI_PRICE_OUTPUT_PER_M` (USD per million tokens, from OpenAI's pricing page) are set in `.env`.
