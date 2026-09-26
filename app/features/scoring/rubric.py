"""Rubric v2 indicators (P1.4): each axis on the rating guide's 0-3 levels.

Every function is pure over an `Evidence` bundle and returns an `Indicator`:
a level (0-3, fractional when averaged; None = not applicable or not rated)
and the evidence behind it. The levels mirror docs/calibration/huong-dan-cham.md
so the engine and the human raters use the same scale.
"""
import statistics
from dataclasses import dataclass

from app.features.scoring.evidence import Evidence


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
