from app.features.scoring.features import AxisFeatures, compute_features
from app.features.scoring.rules_loader import load_rules

WEIGHTS = {"understanding": 0.25, "hypothesis": 0.22, "prompting": 0.18,
           "verification": 0.15, "testing": 0.10, "debugging": 0.10}


def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))


def _understanding(f: AxisFeatures) -> float:
    # NOTE (MVP limitation): problem_read_ratio defaults to 1.0 because the frontend does not
    # yet instrument problem read-time, so U1 (rushed-start) only fires once that signal is sent.
    u1 = -3 if (f.first_prompt_delay_ms is not None and f.first_prompt_delay_ms < 20000
                and f.problem_read_ratio < 0.6) else 0
    u2 = max(-8, -2 * f.u2_hits)
    pre = 20 + (u1 + u2)  # u1, u2 are negative or zero
    return clamp(0, 20, 0.6 * f.explain_score + 0.4 * pre)


def _hypothesis(f: AxisFeatures) -> float:
    base = 8
    cap = 10 if not f.has_hypothesis_before_code else 20
    return clamp(0, cap, base + 4 * f.h1_count - 4 * f.h2_count)


def _prompting(f: AxisFeatures) -> float:
    cap = 12 if f.p1_ratio > 0.3 else 20
    raw = 14 + 2 * f.p3_hits - 2 * f.p1_hits - 3 * f.p2_clusters - 1 * f.p4_hits
    return clamp(0, cap, raw)


def _verification(f: AxisFeatures) -> float:
    raw = (12
           + (8 if f.has_v1 else 0)
           - (8 if f.has_v1b else 0)
           - 4 * f.v2_count
           - (5 if f.has_v3 else 0))
    return clamp(0, 20, raw)


def _testing(f: AxisFeatures) -> float:
    if not f.has_test_run:
        return 0.0
    return clamp(0, 20, 4 * f.t1_count + (4 if f.best_coverage >= 0.7 else 0))


def _debugging(f: AxisFeatures) -> float:
    return clamp(0, 20, 8 + 6 * f.d1_count - 4 * f.d2_count)


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
