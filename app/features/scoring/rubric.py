"""Rubric v2 indicators (P1.4): each axis on the rating guide's 0-3 levels.

Every function is pure over an `Evidence` bundle and returns an `Indicator`:
a level (0-3, fractional when averaged; None = not applicable or not rated)
and the evidence behind it. The levels mirror docs/calibration/huong-dan-cham.md
so the engine and the human raters use the same scale.
"""
import statistics
from dataclasses import dataclass

from app.features.exercises.debug_regions import hit_regions
from app.features.scoring.evidence import Evidence, Reply, code_lines

# A reply's code counts as pasted when this share of its NEW lines (lines the
# student did not already have) shows up in a later snapshot.
PASTE_SHARE = 0.7
# Fewer new lines than this cannot be told apart from coincidence.
MIN_NEW_LINES = 2


@dataclass(frozen=True)
class Indicator:
    level: float | None
    evidence: str = ""
    # Machine-readable why, for feedback and debugging (e.g. "no_ai_use", "after_code").
    reason: str = ""
    # Sub-indicators when an axis is built from several (P2.2 debugging), for the findings.
    parts: dict | None = None


def _latest_judge(ev: Evidence, kind: str) -> dict | None:
    verdicts = ev.judges.get(kind) or []
    return verdicts[-1] if verdicts else None


def _rated(values: list, evidence: list) -> list[tuple[int, str]]:
    evidence = list(evidence or []) + [""] * len(values)
    return [(v, evidence[i] or "") for i, v in enumerate(values) if isinstance(v, int)]


def understanding(ev: Evidence) -> Indicator:
    """Mean explain-back level. Always applicable; None only while unrated."""
    verdict = _latest_judge(ev, "explain")
    rated = _rated(verdict.get("levels") or [], verdict.get("evidence")) if verdict else []
    if not rated:
        return Indicator(None, reason="unrated")
    best = max(rated, key=lambda r: r[0])
    return Indicator(statistics.mean(level for level, _ in rated), best[1])


def hypothesis(ev: Evidence) -> Indicator:
    """Best student hypothesis. Level 3 also needs it logged before the first code edit."""
    first_code = next((e["ts"] for e in ev.events if e["type"] == "CODE_EDIT"), None)
    # Verdicts asked later for hypotheses logged before rubric v2 (see backfill.py).
    backfilled = {v.get("for_ts"): v for v in ev.judges.get("hypothesis", [])}
    candidates = []
    for e in ev.events:
        p = e["payload"]
        if e["type"] != "HYPOTHESIS" or p.get("proposedBy", "user") != "user":
            continue
        if not isinstance(p.get("level"), int) and isinstance(backfilled.get(e["ts"], {}).get("level"), int):
            p = {**p, "level": backfilled[e["ts"]]["level"], "levelEvidence": backfilled[e["ts"]].get("evidence")}
        level, reason = p.get("level"), ""
        if not isinstance(level, int):
            # Only the correct/incorrect verdict (logged before rubric v2, or the judge gave
            # no level): the rating guide caps such hypotheses at level 2.
            level, reason = (2 if p.get("correct") else 1), "verdict_only"
        if level == 3 and first_code is not None and e["ts"] > first_code:
            level, reason = 2, "after_code"
        candidates.append(Indicator(level, p.get("levelEvidence") or p.get("text") or "", reason))
    if not candidates:
        return Indicator(0, reason="no_hypothesis")
    return max(candidates, key=lambda c: c.level)


def prompting(ev: Evidence) -> Indicator:
    """Median prompt level (the rating guide: the level most prompts show)."""
    if not any(e["type"] == "PROMPT" for e in ev.events):
        return Indicator(None, reason="no_ai_use")
    verdict = _latest_judge(ev, "prompts")
    rated = _rated(verdict.get("levels") or [], verdict.get("evidence")) if verdict else []
    if not rated:
        return Indicator(None, reason="unrated")
    median = statistics.median(level for level, _ in rated)
    closest = min(rated, key=lambda r: abs(r[0] - median))
    return Indicator(median, closest[1])


def suite_passed(ev: Evidence) -> bool:
    suite = ev.submit_suite
    return bool(suite and suite.get("total") and suite.get("passed") == suite.get("total"))


def solved(ev: Evidence) -> bool:
    """The whole suite passed at submit; sessions from before the suite ran at
    submit (P1.2) fall back to the student's last run of their own code."""
    suite = ev.submit_suite
    if suite and suite.get("total"):
        return suite_passed(ev)
    runs = _real_runs(ev)
    return bool(runs) and _run_ratio(runs[-1]) == 1.0


def _pasted_lines(ev: Evidence, reply: Reply, block: str) -> set[str]:
    """The block's new lines that landed in the code after the reply (empty = not pasted)."""
    before = set(code_lines(ev.code_at(reply.at_ms) or ""))
    new = [line for line in code_lines(block) if line not in before]
    if len(new) < MIN_NEW_LINES:
        return set()
    for snapshot in ev.snapshots:
        if snapshot.at_ms <= reply.at_ms:
            continue
        present = set(code_lines(snapshot.code))
        hit = {line for line in new if line in present}
        if len(hit) >= PASTE_SHARE * len(new):
            return hit
    return set()


def verification(ev: Evidence) -> Indicator:
    """How the student handled code Ciel gave them; the worst-handled reply counts.

    Pasted unchanged: 0 if the suite fails at submit, 1 if it passes. Pasted then
    changed: 2, or 3 if the suite passes. Not used: 2, or 3 if a later prompt
    questioned that code. N/A when no reply contained a code block.
    """
    code_replies = [(i, r) for i, r in enumerate(ev.replies) if r.blocks]
    if not code_replies:
        return Indicator(None, reason="no_ai_code")
    verdict = _latest_judge(ev, "prompts") or {}
    questioned = list(verdict.get("questions_ai_code") or [])
    passed = solved(ev)
    final = set(code_lines(ev.final_code))
    outcomes = []
    for i, reply in code_replies:
        pasted = next((lines for block in reply.blocks if (lines := _pasted_lines(ev, reply, block))), set())
        if pasted:
            quote = sorted(pasted)[0]
            if pasted <= final:
                outcomes.append(Indicator(1 if passed else 0, quote, "pasted_unchanged"))
            else:
                outcomes.append(Indicator(3 if passed else 2, quote, "pasted_changed"))
        elif any(questioned[i + 1:]):
            later = next(j for j in range(i + 1, len(questioned)) if questioned[j])
            outcomes.append(Indicator(3, ev.replies[later].prompt[:160] if later < len(ev.replies) else "",
                                      "questioned"))
        else:
            outcomes.append(Indicator(2, reason="not_used"))
    return min(outcomes, key=lambda o: o.level)


def _run_ratio(run: dict) -> float:
    payload = run["payload"]
    if "passRatio" in payload:
        return float(payload["passRatio"])
    return 1.0 if payload.get("passed") else 0.0


def _real_runs(ev: Evidence) -> list[dict]:
    """Runs of the student's own code: running the untouched starter proves nothing."""
    return [r for r in ev.runs if not r["payload"].get("isStarter")]


REQUIRED_VALID_TESTS = 3  # junior/senior (P2.3 decision 3)


def testing(ev: Evidence) -> Indicator:
    """P2.3: with the student's tests (STUDENT_TESTS), the mean of valid tests,
    category coverage, mutation score and correctness (the hidden suite); a
    fresher who wrote no tests is scored on correctness only. Without that event
    (sessions before the Tests tab, exercises without it): correctness alone,
    the P1.4 indicator."""
    correctness = _correctness(ev)
    student = next((e["payload"] for e in reversed(ev.events) if e["type"] == "STUDENT_TESTS"), None)
    if student is None:
        return correctness
    tests = student.get("tests") or []
    optional = ev.exercise_level == "fresher"
    valid = sum(1 for t in tests if t.get("valid"))
    wanted = set(student.get("exercise_categories") or [])
    covered = len(set(student.get("categories") or []) & wanted)
    killed, total = student.get("killed", 0), student.get("total", 0)
    parts = {
        "valid": None if optional and not tests else _share_level(valid / max(len(tests), 1 if optional
                                                                                 else REQUIRED_VALID_TESTS)),
        "coverage": None if (optional and not tests) or not wanted else
        3 if covered >= len(wanted) else 2 if covered == len(wanted) - 1 and covered else 1 if covered else 0,
        "mutation": None if (optional and not tests) or not total else _mutation_level(killed / total),
        "correctness": correctness.level,
        "written": len(tests), "valid_count": valid, "killed": killed, "total": total,
    }
    applicable = [parts[k] for k in ("valid", "coverage", "mutation", "correctness") if parts[k] is not None]
    quote = f"{valid}/{len(tests)} valid test(s), {killed}/{total} mutant(s) caught; suite {correctness.evidence}"
    return Indicator(statistics.mean(applicable), quote, correctness.reason, parts)


def _share_level(share: float) -> int:
    return 3 if share >= 1 else 2 if share >= 0.75 else 1 if share >= 0.5 else 0


def _mutation_level(ratio: float) -> int:
    return 3 if ratio >= 1 else 2 if ratio >= 2 / 3 else 1 if ratio >= 1 / 3 else 0


def _correctness(ev: Evidence) -> Indicator:
    """0 never ran / submitted failing nearly all · 1 submitted with a visible test
    failing · 2 visible pass, hidden fail · 3 the whole suite passes."""
    suite = ev.submit_suite
    ran = bool(ev.runs)
    if suite and suite.get("total"):
        passed, total = suite.get("passed", 0), suite["total"]
        quote = f"{passed}/{total}"
        if passed == total:
            return Indicator(3, quote, "all_pass")
        visible_ok = "visibleTotal" in suite and suite.get("visiblePassed") == suite.get("visibleTotal")
        if not ran:
            return Indicator(0, quote, "never_ran")
        if visible_ok:
            return Indicator(2, quote, "hidden_fail")
        if passed / total < 0.5:
            return Indicator(0, quote, "mostly_failing")
        return Indicator(1, quote, "visible_fail")
    # Before the full suite ran at submit (P1.2): only the visible tests are known.
    if not ran:
        return Indicator(0, reason="never_ran")
    last = _run_ratio(ev.runs[-1])
    return Indicator(2 if last == 1.0 else 1 if last > 0 else 0, f"last run {last:.0%}", "no_suite")


def debugging(ev: Evidence) -> Indicator:
    """Implement exercises: N/A without a real failing run. Debug exercises: always scored.
    Not fixed at submit → 0; the visible tests pass but a hidden (edge) test still
    fails → 2 (owner decision 2026-09-26, matches the P1.3 raters); fixed after
    ≥ 4 failing runs → 1, 2-3 → 2, 0-1 → 3.
    A debug exercise with a locate step (P2.2) is scored from four parts instead."""
    fails = failing_runs(ev)
    if ev.exercise_kind != "debug" and fails == 0:
        return Indicator(None, reason="no_failure")
    located = next((e["payload"] for e in ev.events if e["type"] == "LOCATE"), None)
    if ev.exercise_kind == "debug" and located is not None and ev.debug_regions:
        return _debugging_with_locate(ev, located, fails)
    fixed = solved(ev)
    quote = f"{fails} failing run(s)"
    if not fixed:
        if _visible_ok(ev.submit_suite):
            return Indicator(2, quote, "partially_fixed")
        return Indicator(0, quote, "not_fixed")
    return Indicator(_efficiency(fails), quote, "fixed")


def _visible_ok(suite: dict | None) -> bool:
    return bool(suite) and "visibleTotal" in suite and suite.get("visiblePassed") == suite.get("visibleTotal")


def _efficiency(fails: int) -> int:
    return 3 if fails <= 1 else 2 if fails <= 3 else 1


def _located_level(hit: list[bool], hints: int) -> int:
    """Every region hit: 3 / 2 / 1 with 0 / 1 / 2 hints. Some regions hit: 2 without a hint, else 1."""
    if all(hit):
        return max(1, 3 - hints)
    if any(hit):
        return 2 if hints == 0 else 1
    return 0


def _fixed_level(ev: Evidence) -> int:
    """3 full suite passes · 2 visible pass, hidden fail · 1 some visible pass · 0 none."""
    if solved(ev):
        return 3
    suite = ev.submit_suite
    if _visible_ok(suite):
        return 2
    if suite and "visiblePassed" in suite:
        return 1 if suite.get("visiblePassed", 0) > 0 else 0
    real = _real_runs(ev)  # no suite (old sessions): the last real run
    return 1 if real and _run_ratio(real[-1]) > 0 else 0


def _debugging_with_locate(ev: Evidence, located: dict, fails: int) -> Indicator:
    skipped = bool(located.get("skipped"))
    lines = list(located.get("lines") or [])
    hints = int(located.get("hintsUsed") or 0)
    hit = [False] * len(ev.debug_regions) if skipped else hit_regions(ev.debug_regions, lines)
    verdict = _latest_judge(ev, "locate") or {}
    explained = verdict.get("level") if isinstance(verdict.get("level"), int) else (0 if skipped else None)
    fixed = _fixed_level(ev)
    parts = {"located": 0 if skipped else _located_level(hit, hints), "explained": explained, "fixed": fixed,
             "efficiency": _efficiency(fails) if fixed == 3 else None,
             "hit": hit, "hints_used": hints, "skipped": skipped}
    applicable = [parts[k] for k in ("located", "explained", "fixed", "efficiency") if parts[k] is not None]
    reason = "fixed" if fixed == 3 else "partially_fixed" if fixed == 2 else "not_fixed"
    where = "skipped" if skipped else f"lines {', '.join(map(str, lines))}"
    quote = "; ".join(q for q in (where, verdict.get("evidence") or "", f"{fails} failing run(s)") if q)
    return Indicator(statistics.mean(applicable), quote, reason, parts)


def failing_runs(ev: Evidence) -> int:
    """Runs of the student's own code that failed a visible test."""
    return sum(1 for r in _real_runs(ev) if _run_ratio(r) < 1.0)


def prompt_flags(ev: Evidence, name: str) -> list[bool]:
    """A per-prompt flag from the latest prompt verdict (e.g. "asks_for_solution")."""
    verdict = _latest_judge(ev, "prompts") or {}
    return [bool(flag) for flag in verdict.get(name) or []]
