# Learner API (P3.3)

What the system knows about the signed-in student. Ciel uses the brief (P3.5), and the progress page uses the rest (see "Progress page" below).

## `GET /api/learner/me?locale=vi|en`

Requires auth and returns only the caller's own data. `locale` picks the language of `brief` and of `recurring[].practice` (default `vi`). Any other value gets a 422.

```json
{
  "scored_attempts": 8,
  "skills": [
    {"key": "hash-map", "vi": "Bảng băm (dict)", "en": "Hash map", "rating": 1086.0, "attempts": 3},
    {"key": "concurrency", "vi": "Đồng thời, đa luồng", "en": "Concurrency", "rating": 931.0, "attempts": 2}
  ],
  "axes": {"understanding": 2.4, "hypothesis": 1.8, "prompting": 2.0,
           "verification": 1.2, "testing": 0.6, "debugging": null},
  "recurring": [{"code": "no_student_tests", "count": 4,
                 "practice": "viết ít nhất 3 test thuộc các loại khác nhau trước khi Submit"}],
  "window": 5,
  "history": [
    {"date": "2026-09-28T10:12:00Z", "code": "CP-001", "title": "Two-Sum Variations", "overall": 64.5,
     "levels": {"understanding": 2, "hypothesis": 2, "prompting": 1, "verification": 1, "testing": 0, "debugging": null}},
    {"date": "2026-09-30T08:40:00Z", "code": "CP-004", "title": "Fix the Off-By-One Loop", "overall": 71.0,
     "levels": null}
  ],
  "brief": "Học viên đã có 8 bài được chấm.\nKỹ năng mạnh: ..."
}
```

| Field | Meaning |
|---|---|
| `scored_attempts` | Every scored attempt of the student, old v1 reports included. |
| `skills` | Elo rating per skill, highest first. Every skill starts at 1000; ≥ 1050 reads "good" and < 950 "needs practice". `attempts` counts the scored attempts that practised the skill. **Show a skill as rated only when `attempts ≥ 2`.** Below that, the brief does not name it. Labels come in both languages. |
| `axes` | Mean level (0–3) of each axis over the last `window` v2 reports. `null` means the axis never applied in that window (e.g. debugging with no bug to fix). |
| `recurring` | Risk finding codes seen in at least 2 of those reports, most frequent first. Codes are the same as in `feedback.diagnosis` (see [feedback.md](feedback.md)). |
| `recurring[].practice` | The team-reviewed `practice` phrase of that code's feedback template, in `locale`: lower case, starts with a verb. |
| `window` | Number of v2 reports used for `axes` and `recurring` (0–5). |
| `history` | The last 10 scored reports, oldest first: submit time, exercise, overall score (0–100), and axis levels (0–3, `null` per axis when not applicable). `levels` is `null` for old v1 reports: skip them in axis trends but keep them in the score trend. |
| `brief` | Up to 5 lines of plain text, `\n`-separated. Deterministic, with no code, chat text, names or emails. A student with no scored attempt gets one neutral line. |

## Progress page

The P3.5 page ("Tiến độ" / "Progress") shows these sections, built from this endpoint and the dashboard's `recommended`:

- **Skills.** One bar per skill, from `rating`, with a word, never the raw number:
  - ≥ 1050: "tốt" / "good";
  - < 950: "cần luyện" / "needs practice";
  - otherwise "trung bình" / "average".
  - Skills with `attempts < 2` are listed separately as "chưa đủ dữ liệu" / "not enough data yet", without a bar.
- **Axis trends.** One line per axis over `history[].levels` (0–3). Reports with `levels: null` and axes that are `null` are gaps, not zeros. An overall score line over `history[].overall` is also fine.
- **Recurring issues.** "<practice> (count/window)" for each `recurring` item, e.g. "viết ít nhất 3 test thuộc các loại khác nhau trước khi Submit (4/5 bài)". Hide the section when the list is empty.
- **Next exercises.** The dashboard's `recommended`, same as the Dashboard card.
- **Empty state.** When `scored_attempts` is 0, show one line inviting the student to finish a first exercise, plus the next exercises.

Do not show `brief` (it is written for Ciel), Elo numbers, or the predicted success chance.

## How the ratings move

- After each scored attempt, the student's rating on every skill tag of the exercise moves by `32 × (overall/100 − expected)`. `expected = 1 / (1 + 10^((difficulty − rating) / 400))`.
- The exercise difficulty starts at 900 / 1100 / 1300 (fresher / junior / senior). It moves by 8 in the opposite direction, but only on each student's first scored attempt of that exercise, and never for simulated calibration accounts.
- Ratings are derived data. `python -m app.features.learner.rebuild --apply` recomputes them from all reports, for example after a rescore.

## Recommendations

Since P3.4, `GET /api/dashboard` has a `recommended` list: up to 3 next exercises for the signed-in student, best first. It is empty when every exercise is solved.

```json
"recommended": [
  {"code": "CP-006", "title": "Count Word Frequency", "level": "fresher", "kind": "implement",
   "skills": [{"key": "hash-map", "vi": "Bảng băm (dict)", "en": "Hash map"},
              {"key": "string-processing", "vi": "Xử lý chuỗi", "en": "String processing"}],
   "reason_skills": ["string-processing"]}
]
```

- `skills`: the exercise's skill tags, with labels in both languages.
- `reason_skills`: the keys of `skills` that are among the student's weak skills (the same rule as the brief: rated skills with ≥ 2 attempts, excluding the 2 strongest). When it is not empty, show "Luyện: <labels>" / "Practise: <labels>". When it is empty, show no reason.
- The predicted success chance is used for ranking only and is not sent.

**Ranking.** Only exercises the student has not solved are considered, never an exercise already scored. Lower score is better:

`|p − 0.70| − 0.10 × (weak skills practised) − 0.10 × [debug exercise after a debugging risk] + 0.30 × [unfinished attempt started < 24 h ago]`

- `p` is the Elo expected result of the student's mean rating over the exercise's skills against the exercise difficulty.
- Ties go to the exercise code.
- The Feedback page's `diagnosis.candidates` uses the same ranking. It is limited to the level of the exercise just done or one above, and the debug bonus applies only there. The Dashboard ranks every unsolved exercise.
