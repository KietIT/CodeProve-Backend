# Exercise Content: Authoring & Review Guide

Every exercise has one content file, `content/exercises/<CODE>.json`, holding
its reference solution, its tests (visible + hidden) and its mutant bank.
Files are drafted by Claude and reviewed by the team before they can reach the
database. Design: `docs/superpowers/specs/2026-09-24-p1-design.md` (P1.1).

## Trust model

The `review` block inside a content file is a **workflow marker**, not proof
of review: anyone who can push can write any name there, and GitHub does not
require an approving review on `main` (team decision: the owner merges without
waiting). Review is therefore a **team convention**. What is enforced:

1. **`main` only changes through pull requests** (no direct pushes, no force
   pushes, no deletion), so every content change is visible in a PR.
2. **The operator running the sync is the gate.** Only people with EC2 access
   can run it, and the dry run prints the reviewer of every file. Before
   `--apply`, check that each file's reviewer actually reviewed it.
3. **Drafts are never synced** (the marker stops accidental loads).

Content code (reference solutions, mutants) is executed by the validator in
the same hardened sandbox as student code, never in the backend process.

## Workflow

1. **Draft.** Claude writes the file with `"review": {"status": "draft", "author": "claude", "reviewer": null}`.
2. **Validate.** `pytest tests/test_content_files.py -q` must pass (it runs every
   file in the sandbox). Run one file: `pytest tests/test_content_files.py -q -k CP-004`.
3. **Review.** The assigned reviewer (table below) checks the file against the
   checklist, edits it if needed, re-runs the validator, then sets
   `"status": "approved", "reviewer": "<your name as in the table>"`.
   The reviewer must not be the author.
4. **Approve the pull request on GitHub** (leave a review so there is a record,
   see Trust model), then **merge**.
5. **Load into production** (EC2):
   ```bash
   docker exec codeprove_db pg_dump -U codeprove -d codeprove -Fc > ~/pre_content_$(date +%Y%m%d%H%M%S).dump
   docker exec codeprove_backend python -m app.features.content.sync            # dry run
   docker exec codeprove_backend python -m app.features.content.sync --apply    # write
   ```
   Only approved, valid files are written; the dry run lists what will change.

## File format

```json
{
  "code": "CP-004",
  "reference_solution": [
    "def sum_to_n(n):",
    "    total = 0",
    "    for i in range(1, n + 1):",
    "        total += i",
    "    return total"
  ],
  "tests": [
    {"description": "sums the first three", "input": "sum_to_n(3)", "expected": "6",
     "category": "happy", "hidden": false},
    {"description": "zero adds nothing", "input": "sum_to_n(0)", "expected": "0",
     "category": "boundary", "hidden": true}
  ],
  "mutants": [
    {"code": ["def sum_to_n(n):", "    total = 0", "    for i in range(1, n):",
              "        total += i", "    return total"],
     "bug_line": 3, "bug_type": "off-by-one",
     "note_vi": "Vòng lặp dừng trước n nên không cộng n.",
     "note_en": "The loop stops before n, so n is never added."}
  ],
  "review": {"status": "draft", "author": "claude", "reviewer": null}
}
```

- **Code is an array of lines** so GitHub diffs stay readable. `bug_line` is 1-based.
- **`input`** is a Python expression evaluated after the solution is loaded.
- **`expected`** is compared with `repr()` of the returned value (or with the
  printed output): `"6"`, `"'abc'"`, `"[1, 2]"`, `"True"`, `"None"`.
- **Categories:** `happy` (typical), `boundary` (0, 1, empty, first/last, max),
  `edge` (negative, duplicates, None, unusual characters), `error` (only when the
  problem statement defines error behaviour).
- **Counts:** 1–2 visible tests (normally the two existing ones), 5–8 hidden tests
  including at least one `boundary` and one `edge`; 3–5 mutants.
- **`limits`** (optional) lowers the hidden-test minimum to 3–5 for exercises that
  cannot be tested deterministically in the sandbox (e.g. timing-dependent
  concurrency): `"limits": {"min_hidden": 3, "reason": "..."}`. The reviewer must
  agree with the reason.

## What the validator already proves

The reference passes every test; each mutant changes exactly its `bug_line`, is
caught by at least one test and still passes at least one; a debug exercise's
buggy starter fails at least one test; counts, categories and unique test
descriptions. **You do not need to re-check these by hand.**

## Reviewer checklist (what only a human can judge)

- [ ] The reference solution is correct, idiomatic, and solves the problem **as the
      summary states it** (not a different reading of it). For debug exercises it is
      the starter with only the bug fixed.
- [ ] Visible tests show typical cases only; nothing in their descriptions hints at
      the hidden cases.
- [ ] Hidden tests cover the boundary/edge cases a careful student should think of,
      and none depends on an assumption the summary does not state.
- [ ] Each mutant is a bug a real developer (or an AI) could plausibly write, not
      an absurd one.
- [ ] `note_vi` / `note_en` explain each bug in one sentence that makes sense to a
      student after submit, and say the same thing in both languages.
- [ ] If `limits` is used, the reason is real (the exercise truly cannot be tested
      deterministically here).

If an exercise's summary is too ambiguous to test fairly, do not approve it:
write the problem in the PR so the team can fix the summary first.

## Review assignment

| Reviewer | Exercises |
|---|---|
| Kiệt | CP-001 … CP-008 |
| Trung | CP-009 … CP-012, CP-101 … CP-104 |
| Minh | CP-105 … CP-110, CP-201, CP-202 |
| Phát | CP-203 … CP-208 |
