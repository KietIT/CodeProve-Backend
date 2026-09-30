# Report feedback API (P1.4 + P1.5) — contract for the P1.6 frontend

Returned by `POST /api/attempts/{id}/explain-back` and `GET /api/attempts/{id}/report`,
inside `feedback`. Present when the report was scored by engine v2 (`SCORING_ENGINE=v2`);
reports scored by v1 do not have these keys, so the UI must treat them as optional.

**Rule for the UI:** render from `levels`, `diagnosis.findings[*].code/params/text`. Never parse
English sentences (`note`, `step`, `desc`); those old fields stay only until P1.6 ships.

## Submit language

`POST /api/attempts/{id}/submit?locale=vi|en` — the locale is stored with the submission and
the diagnosis texts are written in it. Send the UI language the student is using.

## `feedback.engine`, `feedback.levels`, `feedback.evidence` (P1.4)

```json
"engine": "v2",
"levels": {"understanding": 3, "hypothesis": 2, "prompting": null, "verification": null,
           "testing": 2, "debugging": 3},
"evidence": {"testing": {"evidence": "5/8", "reason": "hidden_fail"}, "...": {}},
"not_applicable": {"prompting": "no_ai_use", "verification": "no_ai_code"}
```

- `levels[axis]`: 0–3 (the rating guide's scale) or `null` = not applicable (reason in
  `not_applicable`). Suggested labels: 0 Chưa đạt / Not yet, 1 Cơ bản / Basic, 2 Khá / Good,
  3 Tốt / Strong. `axes` still carries the 0–20 score (= 20 × level / 3 × integrity multiplier).
- `evidence[axis].reason`: machine code, for debugging and analytics; the student-facing text is
  in the diagnosis.

## `feedback.diagnosis` (P1.5)

```json
"diagnosis": {
  "version": 1,
  "locale": "vi",
  "model": "gpt-4o-mini",
  "candidates": ["CP-105", "CP-003"],
  "findings": [
    {
      "code": "hidden_edge_failed",
      "axis": "testing",
      "kind": "risk",
      "severity": "medium",
      "params": {"failed_categories": ["boundary", "edge"], "failed_tests": ["limit of one"]},
      "evidence": "5/8",
      "text": {
        "what_happened": "...", "why_it_matters": "...",
        "how_to_improve": "...", "try_next": "..."
      },
      "next_exercise": "CP-105",
      "source": "llm"
    }
  ]
}
```

- `findings` is already ranked and trimmed: at most 3 `kind: "risk"` (worst first), then at
  most 2 `kind: "strength"`. Show them in this order.
- `severity`: `high` | `medium` | `low` for risks, `null` for strengths.
- `text`: four plain-text fields in `diagnosis.locale` (no markdown except, rarely, a 1–2 line
  inline code snippet). Render as text, not HTML.
- `next_exercise`: an exercise code the student has not solved (link to it), or `null`.
- `source`: `"llm"` when `text.what_happened` was written for this session (only
  `explain_missing`, `explain_shallow`, `hypothesis_vague` and `prompts_vague`, whose evidence is
  the student's own words); `"template"` otherwise. All other findings always use the template
  line (strengths would restate the solution; counts are stated exactly); `fallback_reason`
  appears only when the writer was asked and its line was rejected. `why_it_matters`,
  `how_to_improve` and `try_next` always come from the team-reviewed templates. The UI does not
  need to show `source`; it is for quality tracking.
- `axis: "overall"` is used only by `integrity_flags`.

### Finding codes

| Axis | Risks | Strengths |
|---|---|---|
| understanding | `explain_missing`, `explain_shallow` | `explain_strong` |
| hypothesis | `no_hypothesis`, `hypothesis_vague`, `hypothesis_after_code` | `hypothesis_strong` |
| prompting | `asked_for_solution` (`count`), `prompts_vague` | `prompts_strong` |
| verification | `pasted_ai_failing`, `pasted_ai_unchecked` | `adapted_ai_code`, `questioned_ai_code` |
| testing | `never_ran_tests`, `submitted_failing` (`passed`, `total`), `hidden_edge_failed` (`failed_categories`, `failed_tests`) | `all_tests_passed` |
| debugging | `bug_not_fixed` (`passed`, `total`), `partial_fix` (`failed_categories`, `failed_tests`), `trial_and_error` (`failing_runs`), `bug_not_located` (`hints_used`), `bug_explanation_weak` | `quick_fix`, `bug_located`, `bug_explained_well` |
| overall | `integrity_flags` (`paste`, `focus_lost`) | |

`failed_categories` values: `happy`, `boundary`, `edge`, `error`, `uncategorized`.
`failed_tests`: names (descriptions) of up to 3 failing hidden tests, never their inputs; may be empty.
A failing submit shows `bug_not_fixed` on debug exercises and `submitted_failing` otherwise, never both.
Source of truth: `app/features/feedback/diagnosis.py` (`FINDING_CODES`), texts in
`app/features/feedback/templates.py`.

## Debug exercises: the locate step (P2.2)

On the 9 debug exercises (`kind: "debug"`) the student first locates the bug, then fixes it.
The step exists when `GET /api/attempts/{id}` returns `debug` non-null.

### Before submit

- `GET /api/attempts/{id}?locale=vi|en` → `debug: {"located": bool, "hints_used": 0-2, "hints": [text, ...]}`
  (`null` on other exercises). `hints` are the hints already bought, in the requested language, so a
  reload restores the step. The editor stays read-only until `located` is true.
- `POST /api/attempts/{id}/debug/hint?locale=vi|en` → `{"step": 1|2, "text": "..."}`. Step 1 is the kind
  of bug, step 2 a line range ("Xem kỹ các dòng 2–4."). 409 after locating, after 2 hints or after submit;
  400 on a non-debug exercise. Each hint lowers the "located" part of the Debugging axis; say so on
  the button.
- `POST /api/attempts/{id}/debug/locate` body `{"lines": [int], "reason": str (≤ 500), "skipped": bool}`
  → `{"ok": true}`. Lines are 1-based lines of the starter **as served** (comments stripped: the code
  the editor shows). Between 1 and `regions + 1` lines, which the UI does not know: allow up to 3 and
  show the 422 `detail` if the server refuses. `skipped: true` records a skip (lines and reason
  ignored). 409 if already located or submitted. The response never says whether the lines were
  right: the answer is revealed after submit.
- The exercise's free hint (`hint`, the "Gợi ý / Hint" accordion) must stay hidden on debug
  exercises until `located` is true: several of those hints name the bug.

### After submit: `feedback.debug`

Present on reports of debug exercises whose attempt has a location (absent otherwise):

```json
"debug": {
  "regions": [[3]],
  "selected": [2, 3],
  "hit": [true],
  "hints_used": 1,
  "skipped": false,
  "explanation": "Dòng 3: range(1, n) dừng trước n ..."
}
```

`regions`: the real bug, as groups of 1-based served-starter lines (several groups = several
issues, e.g. CP-208). `hit[i]`: whether the selection touched `regions[i]`. `explanation` is in the
report's locale. Show the starter with the student's lines and the real ones marked, and the
explanation.

`feedback.evidence.debugging.parts` (for analytics; the UI needs only the level and the findings):
`{"located": 0-3, "explained": 0-3 | null, "fixed": 0-3, "efficiency": 0-3 | null, "hit": [...],
"hints_used": n, "skipped": bool}`. The Debugging level is their mean.
