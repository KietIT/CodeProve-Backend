"""Axis weight selection on the golden set (P1.7).

    python -m app.features.calibration.weights --data DIR --out FILE.md [--floor 0.05]

Recomputes every session's overall from the engine's axis scores under each
candidate weight set (with the engine's own `weighted_overall`), and measures
agreement with the raters' holistic overall level: Spearman (primary), ICC(2,1)
between the engine's tier and the human mean level, and exact tier agreement.
The regression set is judged on leave-one-out predictions. DIR is laid out as
for `analyze.py` (rater exports + engine.json). Pure Python, like
`agreement.py` and `ahp.py`.
"""
import argparse
import math
import random
import statistics
from pathlib import Path

from app.features.attempts.scoring_service import tier_for
from app.features.calibration import ahp
from app.features.calibration.agreement import icc2, pearson, spearman
from app.features.calibration.analyze import AXIS_NAMES, OVERALL_LEVELS, Dump, ahp_section, load_dump
from app.features.scoring.engine import WEIGHTS, weighted_overall

AXES = ahp.AXES
TIERS = ("Emerging", "Developing", "Strong", "Exceptional")  # tier_for's names, lowest first = level 0-3


def candidates(ahp_answers: dict[str, dict]) -> dict[str, dict[str, float]]:
    """The fixed weight sets: current, equal, and the team's AHP (all members,
    and consistent members only when that differs)."""
    sets = {"current": dict(WEIGHTS), "equal": {a: 1 / len(AXES) for a in AXES}}
    section = ahp_section(ahp_answers)
    if section["group_weights"]:
        sets["ahp"] = section["group_weights"]
    if section["group_consistent_weights"]:
        sets["ahp_consistent"] = section["group_consistent_weights"]
    return sets


def human_overall(dump: Dump) -> dict[str, float]:
    """Mean overall level (0-3) per session over the raters who gave one."""
    levels: dict[str, list[int]] = {}
    for sessions in dump.ratings.values():
        for sid, rating in sessions.items():
            if rating.get("overall") in OVERALL_LEVELS:
                levels.setdefault(sid, []).append(OVERALL_LEVELS.index(rating["overall"]))
    return {sid: statistics.mean(values) for sid, values in levels.items()}


def overalls(engine: dict[str, dict], weights: dict[str, float]) -> dict[str, float]:
    return {sid: weighted_overall(entry["axes"], weights) for sid, entry in engine.items()}


def tier_level(overall: float) -> int:
    return TIERS.index(tier_for(overall))


def _half_up(x: float) -> int:
    return math.floor(x + 0.5)


def evaluate(overall_by_session: dict[str, float], human: dict[str, float]) -> dict:
    sessions = sorted(set(overall_by_session) & set(human))
    engine = [overall_by_session[s] for s in sessions]
    people = [human[s] for s in sessions]
    tiers = [tier_level(o) for o in engine]
    icc, _ = icc2([[float(t), h] for t, h in zip(tiers, people)]) if len(sessions) >= 2 else (math.nan, math.nan)
    return {
        "spearman": spearman(engine, people) if len(sessions) >= 3 else math.nan,
        "icc": icc,
        "tier_exact": sum(t == _half_up(h) for t, h in zip(tiers, people)) / len(sessions) if sessions else math.nan,
        # > 0: the engine's tier sits above the raters' level on average (a cutoff question, not a weight one).
        "tier_bias": statistics.mean(t - h for t, h in zip(tiers, people)) if sessions else math.nan,
        "n": len(sessions),
    }


FLOOR = 0.05  # owner decision 2026-09-29: no axis may drop below 5%
_STEPS = (0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001)


def _fit_score(engine: dict[str, dict], human: dict[str, float], sessions: list[str],
               weights: dict[str, float]) -> float:
    r = pearson([weighted_overall(engine[s]["axes"], weights) for s in sessions], [human[s] for s in sessions])
    return -math.inf if math.isnan(r) else r


def _on_floor(weights: dict[str, float], floor: float) -> dict[str, float]:
    """Scale a weight set into the feasible region: every weight >= floor, sum 1."""
    total = sum(weights.values())
    return {a: floor + (1 - len(AXES) * floor) * weights[a] / total for a in AXES}


def _search(start: dict[str, float], score, floor: float) -> tuple[dict[str, float], float]:
    """Derivative-free local search on the simplex: move weight from one axis to
    another while it improves the score, with shrinking steps."""
    w, best = dict(start), score(start)
    for step in _STEPS:
        improved = True
        while improved:
            improved = False
            for give in AXES:
                for take in AXES:
                    amount = min(step, w[give] - floor)
                    if give == take or amount <= 1e-12:
                        continue
                    trial = {**w, give: w[give] - amount, take: w[take] + amount}
                    value = score(trial)
                    if value > best + 1e-12:
                        w, best, improved = trial, value, True
    return w, best


def fit_weights(engine: dict[str, dict], human: dict[str, float], floor: float = FLOOR) -> dict[str, float]:
    """Weights (each >= floor, sum 1) whose overall correlates best (Pearson) with
    the human mean level on the given sessions. Several starts: current, equal,
    and one leaning on each axis; the best local optimum wins."""
    sessions = sorted(set(engine) & set(human))

    def score(weights: dict[str, float]) -> float:
        return _fit_score(engine, human, sessions, weights)

    corner = 1 - (len(AXES) - 1) * floor
    starts = [_on_floor(WEIGHTS, floor), _on_floor({a: 1.0 for a in AXES}, floor),
              *({b: (corner if b == a else floor) for b in AXES} for a in AXES)]
    best_w, best = starts[0], -math.inf
    for start in starts:
        w, value = _search(start, score, floor)
        if value > best:
            best_w, best = w, value
    return best_w


def loo_predictions(engine: dict[str, dict], human: dict[str, float],
                    floor: float = FLOOR) -> tuple[dict[str, float], list[dict[str, float]]]:
    """Leave-one-out: each session's overall under weights fitted without it,
    plus the weights of every fold (to show how stable the fit is)."""
    sessions = sorted(set(engine) & set(human))
    predictions, folds = {}, []
    for held_out in sessions:
        rest = [s for s in sessions if s != held_out]
        w = fit_weights({s: engine[s] for s in rest}, {s: human[s] for s in rest}, floor)
        folds.append(w)
        predictions[held_out] = weighted_overall(engine[held_out]["axes"], w)
    return predictions, folds


def bootstrap_delta(a: dict[str, float], b: dict[str, float], human: dict[str, float],
                    samples: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Paired bootstrap of Spearman(a) - Spearman(b): (mean, 2.5th, 97.5th percentile).
    Resamples sessions, so both sets are always compared on the same sample."""
    sessions = sorted(set(a) & set(b) & set(human))
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        pick = [rng.choice(sessions) for _ in sessions]
        people = [human[s] for s in pick]
        delta = spearman([a[s] for s in pick], people) - spearman([b[s] for s in pick], people)
        if not math.isnan(delta):  # a sample where one side is constant has no rank correlation
            deltas.append(delta)
    if not deltas:
        return math.nan, math.nan, math.nan
    deltas.sort()
    return (round(statistics.mean(deltas), 6), round(deltas[int(0.025 * (len(deltas) - 1))], 6),
            round(deltas[int(0.975 * (len(deltas) - 1))], 6))


# ---------- Selection ----------

MIN_GAIN = 0.02  # a candidate must beat the current weights by this much Spearman
SIMPLICITY = ("current", "equal", "ahp", "ahp_consistent", "regression")  # simplest first


def choose(sets: dict[str, dict]) -> str:
    """The rule fixed in the P1.7 plan: keep `current` unless a set beats it by
    >= MIN_GAIN with a bootstrap interval above 0; of those, the best one, or the
    simplest one within MIN_GAIN of the best."""
    base = sets["current"]["metrics"]["spearman"]
    qualified = [name for name, s in sets.items() if name != "current"
                 and s["metrics"]["spearman"] - base >= MIN_GAIN and s["delta"][1] > 0]
    if not qualified:
        return "current"
    best = max(sets[n]["metrics"]["spearman"] for n in qualified)
    close = [n for n in qualified if best - sets[n]["metrics"]["spearman"] < MIN_GAIN]
    return min(close, key=SIMPLICITY.index)


def analyse_weights(dump: Dump, floor: float = FLOOR, samples: int = 2000, seed: int = 0) -> dict:
    human = human_overall(dump)
    engine = {s: e for s, e in dump.engine.items() if s in human}
    sets: dict[str, dict] = {}
    for name, w in candidates(dump.ahp).items():
        predictions = overalls(engine, w)
        sets[name] = {"weights": w, "predictions": predictions, "metrics": evaluate(predictions, human)}
    loo, folds = loo_predictions(engine, human, floor)
    sets["regression"] = {"weights": fit_weights(engine, human, floor), "predictions": loo, "folds": folds,
                          "metrics": evaluate(loo, human)}
    for name, s in sets.items():
        s["delta"] = ((0.0, 0.0, 0.0) if name == "current" else
                      bootstrap_delta(s["predictions"], sets["current"]["predictions"], human, samples, seed))
    chosen = choose(sets)
    # What students would see change: the tier under the shipped weights (regression: fitted on all sessions).
    shipped = overalls(engine, sets[chosen]["weights"])
    changes = [{"session": s, "from": tier_level(sets["current"]["predictions"][s]), "to": tier_level(shipped[s]),
                "human": human[s]}
               for s in sorted(engine) if tier_level(sets["current"]["predictions"][s]) != tier_level(shipped[s])]
    return {"n": len(engine), "raters": sorted(dump.ratings), "ahp_members": sorted(dump.ahp), "floor": floor,
            "samples": samples, "sets": sets, "chosen": chosen, "tier_changes": changes}


# ---------- Markdown ----------

SET_NAMES = {"current": "Hiện tại", "equal": "Đều nhau", "ahp": "AHP nhóm", "ahp_consistent": "AHP (CR < 0,1)",
             "regression": "Hồi quy"}
_WEIGHT_NOTE = {"regression": " (fit trên toàn bộ lượt)"}
_METRIC_NOTE = {"regression": " (leave-one-out)"}


def _num(value: float, digits: int = 3) -> str:
    return "—" if value is None or math.isnan(value) else f"{value:.{digits}f}".replace(".", ",")


def render_weights(result: dict) -> str:
    sets = result["sets"]
    out = ["# Chọn trọng số các trục (P1.7)", "",
           f"- Lượt làm bài: {result['n']} · Người chấm: {len(result['raters'])} · "
           f"AHP: {', '.join(result['ahp_members']) or 'không có'}",
           f"- Quy tắc: giữ trọng số hiện tại trừ khi một bộ hơn ≥ {_num(MIN_GAIN, 2)} Spearman và khoảng "
           f"bootstrap ({result['samples']} mẫu) của phần chênh lớn hơn 0; trong các bộ đạt, chọn bộ tốt nhất, "
           f"hoặc bộ đơn giản nhất nếu kém bộ tốt nhất < {_num(MIN_GAIN, 2)}.", "",
           "## Trọng số", "", "| Bộ | " + " | ".join(AXIS_NAMES[a] for a in AXES) + " |",
           "|---|" + "---|" * len(AXES)]
    for name, s in sets.items():
        out.append(f"| {SET_NAMES.get(name, name)}{_WEIGHT_NOTE.get(name, '')} | "
                   + " | ".join(f"{100 * s['weights'][a]:.0f}%" for a in AXES) + " |")
    folds = sets["regression"]["folds"]
    if folds:
        out.append("| Hồi quy: dao động qua các fold | " + " | ".join(
            f"{100 * min(f[a] for f in folds):.0f}–{100 * max(f[a] for f in folds):.0f}%" for a in AXES) + " |")
    out += ["", "## Mức khớp với người chấm", "",
            "| Bộ | Spearman | Chênh so với hiện tại (95% bootstrap) | ICC(2,1) tier | Khớp tier | Lệch tier TB |",
            "|---|---|---|---|---|---|"]
    for name, s in sets.items():
        m, (_, low, high) = s["metrics"], s["delta"]
        delta = "—" if name == "current" else f"{_num(m['spearman'] - sets['current']['metrics']['spearman'])} " \
                                               f"({_num(low)} đến {_num(high)})"
        out.append(f"| {SET_NAMES.get(name, name)}{_METRIC_NOTE.get(name, '')} | {_num(m['spearman'])} | {delta} | "
                   f"{_num(m['icc'])} | {_num(100 * m['tier_exact'], 0)}% | {_num(m['tier_bias'], 2)} |")
    out += ["", "Lệch tier TB = tier của engine (0–3) trừ mức trung bình của người chấm; > 0 là engine xếp cao hơn. "
            "Độ lệch này phụ thuộc chủ yếu vào ngưỡng tier (50/70/85); P1.7 không đổi ngưỡng."]
    chosen = result["chosen"]
    out += ["", f"## Bộ được chọn: **{SET_NAMES.get(chosen, chosen)}** (`{chosen}`)", ""]
    if chosen == "current":
        out.append("Không bộ nào vượt trọng số hiện tại đủ rõ theo quy tắc: giữ nguyên, không cần rescore.")
    else:
        out.append(f"{len(result['tier_changes'])}/{result['n']} lượt đổi tier so với trọng số hiện tại:")
        out += ["", "| Lượt | Tier hiện tại | Tier mới | Mức người chấm (TB) |", "|---|---|---|---|"]
        out += [f"| {c['session']} | {TIERS[c['from']]} | {TIERS[c['to']]} | {_num(c['human'], 2)} |"
                for c in result["tier_changes"]]
    out += ["", "## Hạn chế", "",
            "- Bộ mẫu là các lượt mô phỏng, viết để trải đều các mức, nên mức khớp có thể cao hơn khi áp vào bài thật.",
            "- Người chấm cũng là người xây hệ thống; mức tổng thể của họ có thể nghiêng theo cách engine chấm.",
            f"- AHP chỉ gồm {len(result['ahp_members'])} người.",
            f"- Hồi quy giữ mỗi trục ≥ {100 * result['floor']:.0f}% và được đánh giá bằng leave-one-out; "
            "trọng số dùng thật là bộ fit trên toàn bộ lượt."]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--floor", type=float, default=FLOOR)
    parser.add_argument("--samples", type=int, default=2000)
    args = parser.parse_args()
    result = analyse_weights(load_dump(args.data), floor=args.floor, samples=args.samples)
    args.out.write_text(render_weights(result), encoding="utf-8")
    print(f"written {args.out}: chosen {result['chosen']}")


if __name__ == "__main__":
    main()
