from app.features.scoring.features import AxisFeatures, compute_features

# PROVISIONAL: chosen by the team, not derived. P1 replaces them with AHP
# weights benchmarked against equal weights, then validates on the golden set
# (docs/superpowers/specs/2026-09-24-scoring-roadmap.md, "Axis weights").
WEIGHTS = {"understanding": 0.25, "hypothesis": 0.22, "prompting": 0.18,
           "verification": 0.15, "testing": 0.10, "debugging": 0.10}

# Why an axis is "not applicable" (None): the session gave no opportunity to
# observe that skill, which is not the same as the student being weak at it.
# N/A axes are excluded from `overall` (the remaining weights renormalise).
NA_REASONS = {
    "prompting": "no_ai_use",
    "verification": "no_ai_code",
    "debugging": "no_failure",
}


def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))


# ── Scoring philosophy (rev. 2026-09-24, P0) ─────────────────────────────────
# Every axis is earned from evidence. An axis the session had no opportunity to
# show is N/A rather than 0. The constants below are interim: phase P1 replaces
# them with evidence-centred rubrics (docs/superpowers/specs/2026-09-24-scoring-roadmap.md).

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
    # No hypothesis logged => 0 (the hypothesis box is always available).
    # Correctness dominates; AI-proposed hypotheses subtract.
    if f.hypothesis_count == 0:
        return 0.0
    raw = 3 + 9 * f.h1_count + (5 if f.has_hypothesis_before_code else 0) - 4 * f.h2_count
    return clamp(0, 20, raw)


def _prompting(f: AxisFeatures) -> float | None:
    if f.prompt_count == 0:
        return None
    cap = 12 if f.p1_ratio > 0.3 else 20
    raw = 10 + 3 * f.p3_hits - 2 * f.p1_hits - 3 * f.p2_clusters - 1 * f.p4_hits
    return clamp(0, cap, raw)


def _verification(f: AxisFeatures) -> float | None:
    # Verifying AI output needs AI output: with no code-bearing reply and no
    # planted trap there is nothing to verify, so the axis is N/A.
    if not (f.ai_code_received or f.trap_injected):
        return None
    earned = (12 if f.has_v1 else 0) + (8 if f.tested_after_ai_code else 0)
    possible = 8 + (12 if f.trap_injected else 0)
    penalty = (10 if f.has_v1b else 0) + 4 * f.v2_count + (6 if f.has_v3 else 0)
    return clamp(0, 20, 20 * earned / possible - penalty)


def _testing(f: AxisFeatures) -> float:
    # Interim until students write their own tests (P2): how much of the full
    # suite (visible + hidden) the submitted code passes. Sessions without a
    # submit suite (older ones) fall back to the last run of the visible tests.
    if f.submit_tests and f.submit_tests.get("total"):
        # passed/total, not the stored passRatio, which is rounded to 3 places.
        return clamp(0, 20, 20 * f.submit_tests["passed"] / f.submit_tests["total"])
    if f.run_count == 0:
        return 0.0
    return clamp(0, 20, 20 * f.final_pass_ratio)


def _debugging(f: AxisFeatures, exercise_kind: str) -> float | None:
    # Debug-kind exercises start broken, so there is always something to debug.
    # On implement exercises only a real failing run of the student's own code
    # creates that opportunity; a first-try pass is N/A, not a weakness.
    fails = f.real_fails_before_first_pass
    is_debug = exercise_kind == "debug"
    if not is_debug and fails == 0:
        return None
    if not f.any_pass:
        return 0.0
    if is_debug:
        return clamp(12, 20, 20 - 2 * fails)
    # Tops out at 16 so needing fixes never beats an otherwise equal clean solve.
    return clamp(10, 16, 16 - 2 * (fails - 1))


def integrity_multiplier(f: AxisFeatures) -> float:
    """Scale every axis down when the session shows cheating signals.

    Pasting an answer from another AI is the exact abuse this platform exists to
    catch, so each paste (blocked or burst) is weighted heavily; leaving the tab
    to copy from elsewhere (FOCUS_LOST) is a softer signal. With no flags the
    multiplier is 1.0, so honest attempts are unaffected.
    """
    penalty = 0.12 * f.paste_flags + 0.06 * f.focus_lost
    return clamp(0.4, 1.0, 1.0 - penalty)


def score_attempt(events: list[dict], explain_score: float | None, exercise_kind: str = "implement") -> dict:
    f = compute_features(events, explain_score)
    mult = integrity_multiplier(f)
    raw: dict[str, float | None] = {
        "understanding": _understanding(f),
        "hypothesis": _hypothesis(f),
        "prompting": _prompting(f),
        "verification": _verification(f),
        "testing": _testing(f),
        "debugging": _debugging(f, exercise_kind),
    }
    # The integrity multiplier applies to every scored axis so a compromised
    # session cannot report "Strong understanding" off a pasted explanation.
    axes = {a: (round(v * mult, 2) if v is not None else None) for a, v in raw.items()}
    active = {a: v for a, v in axes.items() if v is not None}
    total_weight = sum(WEIGHTS[a] for a in active)
    overall = round(5 * sum((WEIGHTS[a] / total_weight) * v for a, v in active.items()), 2) if total_weight else 0.0
    return {
        "axes": axes,
        "overall": clamp(0, 100, overall),
        "features": f,
        "integrity_multiplier": mult,
        "not_applicable": {a: NA_REASONS[a] for a, v in axes.items() if v is None},
    }
