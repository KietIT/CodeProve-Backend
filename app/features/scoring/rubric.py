"""Rubric v2 indicators (P1.4): each axis on the rating guide's 0-3 levels.

Every function is pure over an `Evidence` bundle and returns an `Indicator`:
a level (0-3, fractional when averaged; None = not applicable or not rated)
and the evidence behind it. The levels mirror docs/calibration/huong-dan-cham.md
so the engine and the human raters use the same scale.
"""
import statistics
from dataclasses import dataclass

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
    candidates = []
    for e in ev.events:
        p = e["payload"]
        if e["type"] != "HYPOTHESIS" or p.get("proposedBy", "user") != "user":
            continue
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
    passed = suite_passed(ev)
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
