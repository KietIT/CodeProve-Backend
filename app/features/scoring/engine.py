from app.features.scoring.features import AxisFeatures, compute_features
from app.features.scoring.rules_loader import load_rules

WEIGHTS = {"understanding": 0.25, "hypothesis": 0.22, "prompting": 0.18,
           "verification": 0.15, "testing": 0.10, "debugging": 0.10}


def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))


# ── Scoring philosophy (rev. 2026-07-01) ─────────────────────────────────────
# Every axis is EARNED FROM ZERO: a candidate only scores by producing evidence
# of that competency. An untouched attempt (no code, no hypothesis, no prompt,
# no test, no real explanation) scores 0 on every axis and 0 overall - there is
# no "baseline" credit for showing up. Penalties then push earned scores down.

def _understanding(f: AxisFeatures) -> float:
    # Driven almost entirely by the explain-back score (0-20, LLM-judged). The
    # small engagement bonus is tied to actually SOLVING (a fully-passing run),
    # not to typing characters - so gibberish like "asfasdf" earns nothing.
    # Shallow concept-only prompts and a rushed start reduce it.
    u1 = -3 if (f.first_prompt_delay_ms is not None and f.first_prompt_delay_ms < 20000
                and f.problem_read_ratio < 0.6) else 0
    engage = 2 if f.any_pass else 0
    return clamp(0, 20, 0.9 * f.explain_score + engage - 2 * f.u2_hits + u1)


def _hypothesis(f: AxisFeatures) -> float:
    # No hypothesis logged => 0. Correctness dominates: a WRONG hypothesis earns
    # only a small credit for the habit, while a correct one - especially logged
    # before coding - earns most of the axis. AI-proposed hypotheses subtract.
    if f.hypothesis_count == 0:
        return 0.0
    raw = 3 + 9 * f.h1_count + (5 if f.has_hypothesis_before_code else 0) - 4 * f.h2_count
    return clamp(0, 20, raw)


def _prompting(f: AxisFeatures) -> float:
    # No prompt to Ciel => 0 (no prompting skill demonstrated). Otherwise reward
    # constraint-aware, keyword-rich prompts; penalise lazy / duplicate ones.
    if f.prompt_count == 0:
        return 0.0
    cap = 12 if f.p1_ratio > 0.3 else 20
    raw = 10 + 3 * f.p3_hits - 2 * f.p1_hits - 3 * f.p2_clusters - 1 * f.p4_hits
    return clamp(0, cap, raw)


def _verification(f: AxisFeatures) -> float:
    # Earned by catching the planted bug and/or verifying with tests. Nothing
    # verified => 0. Accepting buggy AI code or paste-blind behaviour subtracts.
    credit = ((10 if f.has_v1 else 0)
              + (4 if f.has_test_run else 0)
              + (4 if f.best_coverage >= 0.7 else 0))
    penalty = ((10 if f.has_v1b else 0)
               + 4 * f.v2_count
               + (6 if f.has_v3 else 0))
    return clamp(0, 20, credit - penalty)


def _testing(f: AxisFeatures) -> float:
    if not f.has_test_run:
        return 0.0
    return clamp(0, 20, 4 * f.t1_count + (4 if f.best_coverage >= 0.7 else 0))


def _debugging(f: AxisFeatures) -> float:
    # No fail -> fix -> pass cycle => 0 (no debugging demonstrated).
    if f.d1_count == 0:
        return 0.0
    return clamp(0, 20, 6 + 8 * f.d1_count - 4 * f.d2_count)


def integrity_multiplier(f: AxisFeatures) -> float:
    """Scale every axis down when the session shows cheating signals.

    Pasting an answer from another AI is the exact abuse this platform exists to
    catch, so each paste (blocked or burst) is weighted heavily; leaving the tab
    to copy from elsewhere (FOCUS_LOST) is a softer signal. With no flags the
    multiplier is 1.0, so honest attempts are unaffected.
    """
    penalty = 0.12 * f.paste_flags + 0.06 * f.focus_lost
    return clamp(0.4, 1.0, 1.0 - penalty)


def score_attempt(
    events: list[dict],
    explain_score: float | None,
    testing_enabled: bool = True,
    debugging_enabled: bool = True,
) -> dict:
    load_rules()  # ensures rule files are valid/loaded
    f = compute_features(events, explain_score)
    mult = integrity_multiplier(f)
    # Apply the integrity multiplier to every axis so a compromised session cannot
    # report "Strong understanding" off a pasted explanation, then derive overall
    # from the penalised axes so the headline number reflects it too.
    axes: dict[str, float | None] = {
        "understanding": round(_understanding(f) * mult, 2),
        "hypothesis": round(_hypothesis(f) * mult, 2),
        "prompting": round(_prompting(f) * mult, 2),
        "verification": round(_verification(f) * mult, 2),
        "testing": round(_testing(f) * mult, 2) if testing_enabled else None,
        "debugging": round(_debugging(f) * mult, 2) if debugging_enabled else None,
    }
    active = {a: v for a, v in axes.items() if v is not None}
    total_weight = sum(WEIGHTS[a] for a in active)
    overall = round(5 * sum((WEIGHTS[a] / total_weight) * v for a, v in active.items()), 2) if total_weight else 0.0
    return {"axes": axes, "overall": clamp(0, 100, overall), "features": f, "integrity_multiplier": mult}
