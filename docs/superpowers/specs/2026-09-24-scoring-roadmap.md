# Scoring, Feedback & AI Tutor Roadmap (P−1 → P3)

Agreed 2026-09-24. This is the **merged roadmap**: the initial analysis plus
the product owner's review of it. Every phase plan in `docs/superpowers/plans/`
MUST be built from this list and MUST contain a traceability table mapping each
item of its phase to the task(s) that implement it (or state why it moved).

Source tags: **[1]** initial analysis · **[2]** product owner's review ·
**[+]** found during research.

## Problems found (evidence)

- Engine treats "no evidence" as "weak": a one-shot correct solve scores
  Debugging 0 and never above ~90 overall; a student who fails twice then fixes
  outscores them (simulated: 53 vs 72), and fail/pass toggling farms Debugging.
- Testing counts the exercise author's cases (every exercise has 2 visible
  cases, 0 hidden), so Testing is capped at 12/20 for everyone. "coverage" is
  actually the pass ratio. Students never write tests.
- Three overlapping "find the bug" mechanisms (Daily Bug Hunt, 9 debug-kind
  exercises, Ciel's injected bug). Debug starters leak the answer in comments;
  the UI labels the trapped Ciel reply; the trap is "caught" by any later edit.
- Feedback is generic ("Improve your understanding") with no evidence or action.
- "Phòng luyện" personalisation is a static heuristic; Ciel has no memory.
- Formulas are ad-hoc, unvalidated; YAML rules are loaded but unused.

## P−1 — Security & data safety (done: PR #8, #9)

- [+] Sandbox no longer leaks backend secrets; `/practice/trace` requires login; sandbox rate limit; all secrets rotated
- [2] DB and backend ports bound to loopback; DB password rotated on the existing volume
- [2] Daily `pg_dump` to S3 + verified restore tooling (`scripts/backup_db.sh`, `scripts/restore_db.sh`)

## P0 — Quick scoring fixes

- [1] Axes with no opportunity become N/A instead of 0 (Debugging; Prompting / Verification when Ciel is not used), overall renormalises
- [1] Debugging anti-farm (only real failures of the student's own code count; nothing after the first pass counts)
- [1] Interim Testing score independent of how many cases the author wrote
- [1] Pass the right axis enable/applicability to the engine (replaced by evidence-based applicability + exercise kind)
- [1] Remove answer-leaking comments from debug starters
- [1] Remove the UI label that reveals the trapped Ciel reply
- [1] Remove the unused YAML rule files
- [1] Rescore existing reports
- [2] Keep the current axis weights (25/22/18/15/10/10) but mark them as provisional in code and docs: they were chosen by the team, not derived

## Axis weights: how they get a real basis

There is no mathematical proof for the weights of a composite score; they come
either from structured expert judgement or from data. The plan uses both, in
this order, always benchmarked against equal weights (with small samples, unit
weights routinely match regression weights: Dawes 1979, "The robust beauty of
improper linear models").

- P1: weights v1 from AHP (Saaty): 3–5 experts give pairwise comparisons,
  priorities from the principal eigenvector, consistency ratio < 0.1 required.
  AHP priorities are ratio-scale, so renormalising over non-N/A axes preserves
  the experts' ratios. Publish the method on the scoring explainer page.
- End of P1 / P2: once the golden set has 30–50 sessions, pick between AHP,
  equal and constrained-regression weights by agreement with the human
  holistic ratings (Spearman / ICC); prefer the simpler one when the difference
  is small. Axes measured less reliably (e.g. the LLM-judged explain-back vs
  humans) get less weight.
- P3: periodic recalibration as data grows.

## P1 — Exercise data + evidence-based scoring and feedback

- [2] Reference solution, 5–8 categorised hidden tests and a mutant bank for all 30 exercises
- [2] Rewrite each axis as an evidence-centred rubric (ECD)
- [+] The Prompting rubric must not make skipping Ciel advantageous. P0 finding: with Prompting N/A when Ciel is unused, a first-try solve without Ciel scores 90.26 while the same solve plus one good prompt scores 84.2 (the interim formula gives that prompt 13/20). Good prompts must be able to reach 16–20; if that is not enough, reconsider making Ciel use required on selected exercises
- [1] Evidence-based diagnosis layer + LLM-written actionable feedback (what happened / why it matters / how to improve / what to do next) + template fallback; frontend stops regex-matching English notes
- [2] Show levels instead of decimal scores
- [2] Hidden-test display policy: failing category on submit, full input on the Feedback page
- [2] Start a golden set of 30–50 sessions rated by 2–3 humans to validate the rubric and the explain-back LLM judge
- [2] Axis weights v1 via AHP (3–5 experts, consistency ratio < 0.1), benchmarked against equal weights; method published
- [2] (end of P1 / P2) Choose AHP vs equal vs constrained-regression weights by agreement with the golden set

## P2 — New exercise mechanics

- [2] "Tests" tab: short explainer, structured form (type / input / expected / why), checklist, live validity check against the reference solution, mutation-score grading shown after submit, learning mode for fresher
- [1] "Review AI code" mode for debug exercises: pick the buggy line, fix it, see the answer after submit
- [2] New Ciel trap: served from the mutant bank, student must pick the line, outcome-based scoring, random 40–70% bug rate, Youden H − F, generic "AI can be wrong" note on every code reply, reveal after submit
- [1] Proper Debugging scoring for debug exercises

## P3 — AI Tutor + infrastructure

- [1] Skill tags per exercise
- [2] Elo learner model + a compact learner brief (~150–300 tokens) for the LLM, never the full history
- [1] Algorithmic next-exercise recommendation
- [1] Ciel with memory, scaffolded hints by level, progress reports
- [2] Cost controls: prompt layout for caching, model tiering, per-user quotas
- [2] Privacy: PII scrubbing, pseudonymisation, `store=false`, privacy policy + consent + opt-out of AI personalisation, PDPL legal review
- [2] Move the DB to RDS
- [2] `events` partitioning, data retention policy, account deletion API
- [2] Periodically recalibrate weights as data grows (refinement of the P1 choice)
- [1] (later) AI-generated exercise variants
