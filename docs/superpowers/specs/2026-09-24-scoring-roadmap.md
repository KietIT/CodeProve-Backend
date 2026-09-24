# Scoring, Feedback & AI Tutor Roadmap (P−1 → P3)

Agreed 2026-09-24 after a review of the scoring engine, the practice room and
user testing feedback. Each phase gets its own plan in `docs/superpowers/plans/`.

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

## Phases

| Phase | Scope |
|---|---|
| **P−1** (done: #8, #9) | Sandbox secret leak fixed, sandbox auth + rate limit, secrets rotated, DB/backend ports loopback-only, DB password rotated, S3 backup + verified restore |
| **P0** | Axes with no opportunity become N/A (Debugging; Prompting/Verification when Ciel unused); Debugging anti-farm; interim Testing independent of case count; strip answer-leaking comments from debug starters; stop exposing / labelling the trap; delete dead YAML rules; rescore existing reports |
| **P1** | Reference solutions, 5–8 categorised hidden tests and a mutant bank for all 30 exercises; rewrite axes as evidence-centred rubrics; evidence-based diagnosis + LLM-written actionable feedback with template fallback; show levels instead of decimals; hidden-test result display policy; start a 30–50 session golden set rated by humans |
| **P2** | "Tests" tab (guidance, structured form, checklist, live validity check, mutation score, learning mode for fresher); "Review AI code" mode for debug exercises (pick the line, fix, reveal); new Ciel trap (mutant bank, pick line, outcome-based, random 40–70% rate, Youden H − F, generic "AI can be wrong" on all code); proper Debugging for debug exercises |
| **P3** | Skill tags; Elo learner model + compact learner brief for the LLM; algorithmic next-exercise recommendation; Ciel memory and scaffolded hints; progress reports; cost controls (prompt caching layout, model tiering, quotas); privacy (PII scrubbing, pseudonymisation, `store=false`, policy + consent + opt-out, PDPL review); RDS migration, `events` partitioning, retention, account deletion; calibrate weights on the golden set; later AI-generated exercise variants |
