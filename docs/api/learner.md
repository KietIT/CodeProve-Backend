# Learner API (P3.3)

What the system knows about the signed-in student. The P3.5 progress page and Ciel will use it. There is no UI for it yet.

## `GET /api/learner/me?locale=vi|en`

Requires auth and returns only the caller's own data. `locale` picks the language of `brief` (default `vi`). Any other value gets a 422.

```json
{
  "scored_attempts": 8,
  "skills": [
    {"key": "hash-map", "vi": "Bảng băm (dict)", "en": "Hash map", "rating": 1086.0, "attempts": 3},
    {"key": "concurrency", "vi": "Đồng thời, đa luồng", "en": "Concurrency", "rating": 931.0, "attempts": 2}
  ],
  "axes": {"understanding": 2.4, "hypothesis": 1.8, "prompting": 2.0,
           "verification": 1.2, "testing": 0.6, "debugging": null},
  "recurring": [{"code": "no_student_tests", "count": 4}],
  "window": 5,
  "brief": "Học viên đã có 8 bài được chấm.\nKỹ năng mạnh: ..."
}
```

| Field | Meaning |
|---|---|
| `scored_attempts` | Every scored attempt of the student, old v1 reports included. |
| `skills` | Elo rating per skill, highest first. Every skill starts at 1000; ≥ 1050 reads "good" and < 950 "needs practice". `attempts` counts the scored attempts that practised the skill. **Show a skill as rated only when `attempts ≥ 2`.** Below that, the brief does not name it. Labels come in both languages. |
| `axes` | Mean level (0–3) of each axis over the last `window` v2 reports. `null` means the axis never applied in that window (e.g. debugging with no bug to fix). |
| `recurring` | Risk finding codes seen in at least 2 of those reports, most frequent first. Codes are the same as in `feedback.diagnosis` (see [feedback.md](feedback.md)). |
| `window` | Number of v2 reports used for `axes` and `recurring` (0–5). |
| `brief` | Up to 5 lines of plain text, `\n`-separated. Deterministic, with no code, chat text, names or emails. A student with no scored attempt gets one neutral line. |

## How the ratings move

- After each scored attempt, the student's rating on every skill tag of the exercise moves by `32 × (overall/100 − expected)`. `expected = 1 / (1 + 10^((difficulty − rating) / 400))`.
- The exercise difficulty starts at 900 / 1100 / 1300 (fresher / junior / senior). It moves by 8 in the opposite direction, but only on each student's first scored attempt of that exercise, and never for simulated calibration accounts.
- Ratings are derived data. `python -m app.features.learner.rebuild --apply` recomputes them from all reports, for example after a rescore.
