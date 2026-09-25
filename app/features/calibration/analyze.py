"""Golden-set analysis report (P1.3): AHP weights, rater agreement, engine vs humans.

    python -m app.features.calibration.analyze --data DIR --out FILE.md

DIR holds the rating page's database dumped with ArtifactData (`out_dir`):
`ahp/<rater>.json` and `ratings/<rater>/items/<session>.json`, plus the
private export files `engine.json` and `keys.json`. For the simulated set it
may also hold `state.json` (script id -> attempt id) and `profiles.json`
(intended levels per script), which adds an intended-vs-human check.
"""
import argparse
import json
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from app.features.calibration import ahp
from app.features.calibration.agreement import icc2, mean_pairwise_kappa, spearman
from app.features.scoring.engine import WEIGHTS

AXES = ahp.AXES
OVERALL_LEVELS = ("emerging", "developing", "strong", "exceptional")
KAPPA_TARGET = 0.6
AXIS_NAMES = {"understanding": "Thấu hiểu", "hypothesis": "Giả thuyết", "prompting": "Prompting",
              "verification": "Kiểm chứng", "testing": "Testing", "debugging": "Debug"}


@dataclass
class Dump:
    ahp: dict[str, dict] = field(default_factory=dict)            # rater -> answers {"a|b": value}
    ratings: dict[str, dict[str, dict]] = field(default_factory=dict)  # rater -> session -> rating
    engine: dict[str, dict] = field(default_factory=dict)         # session -> {overall, axes}
    intended: dict[str, dict] = field(default_factory=dict)       # session -> intended profile


def _read(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    # ArtifactData may save a document wrapped as {"id", "data", "version", ...}.
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict) and "id" in obj:
        return obj["data"]
    return obj


def load_dump(directory: Path) -> Dump:
    dump = Dump()
    for path in sorted((directory / "ahp").glob("*.json")):
        doc = _read(path)
        if isinstance(doc.get("answers"), dict):
            dump.ahp[path.stem] = doc["answers"]
    for rater_dir in sorted(p for p in (directory / "ratings").glob("*") if p.is_dir()):
        items = {p.stem: _read(p) for p in sorted((rater_dir / "items").glob("*.json"))}
        if items:
            dump.ratings[rater_dir.name] = items
    if (directory / "engine.json").exists():
        dump.engine = _read(directory / "engine.json")
    needed = ("keys.json", "state.json", "profiles.json")
    if all((directory / name).exists() for name in needed):
        keys, state, profiles = (_read(directory / name) for name in needed)
        script_by_attempt = {rec.get("attempt_id"): sid for sid, rec in state.get("sessions", {}).items()}
        for session_id, attempt_id in keys.items():
            script = script_by_attempt.get(attempt_id)
            if script in profiles:
                dump.intended[session_id] = profiles[script]
    return dump


def _ahp_section(answers_by_rater: dict[str, dict]) -> dict:
    members, matrices = {}, {}
    for rater, answers in answers_by_rater.items():
        try:
            m = ahp.matrix({(a, b): answers[f"{a}|{b}"] for a, b in ahp.PAIRS})
        except (KeyError, ValueError) as exc:
            members[rater] = {"error": str(exc)}
            continue
        w = ahp.priorities(m)
        members[rater] = {"weights": dict(zip(AXES, w)), "cr": ahp.consistency_ratio(m)}
        matrices[rater] = m

    def group(raters: list[str]) -> dict[str, float] | None:
        if not raters:
            return None
        return dict(zip(AXES, ahp.priorities(ahp.aggregate([matrices[r] for r in raters]))))

    consistent = [r for r in matrices if members[r]["cr"] < ahp.CR_THRESHOLD]
    return {
        "members": members,
        "group_weights": group(list(matrices)),
        "group_consistent_weights": group(consistent) if len(consistent) != len(matrices) else None,
        "current_weights": dict(WEIGHTS),
        "equal_weights": {a: 1 / len(AXES) for a in AXES},
    }


def _level(value: object) -> int | None:
    return value if isinstance(value, int) and 0 <= value <= 3 else None


def _majority_na(levels: list[int | None]) -> bool:
    return sum(v is None for v in levels) * 2 > len(levels)


def analyse(dump: Dump) -> dict:
    raters = sorted(dump.ratings)
    rated = set().union(*(set(r) for r in dump.ratings.values())) if raters else set()
    sessions = sorted(set(dump.engine) or rated)
    complete = [s for s in sessions if all(s in dump.ratings[r] for r in raters)] if raters else []
    missing = {r: sum(s not in dump.ratings[r] for s in sessions) for r in raters}

    def overall_level(rating: dict) -> int | None:
        key = rating.get("overall")
        return OVERALL_LEVELS.index(key) if key in OVERALL_LEVELS else None

    result: dict = {
        "counts": {"raters": len(raters), "sessions": len(sessions), "complete": len(complete)},
        "missing": {r: n for r, n in missing.items() if n},
        "raters": raters,
        "ahp": _ahp_section(dump.ahp),
        "axes": {},
        "overall": {},
    }

    # Overall level: ICC on the sessions every rater scored.
    rows = [[overall_level(dump.ratings[r][s]) for r in raters] for s in complete]
    rows = [row for row in rows if None not in row]
    if len(raters) >= 2 and len(rows) >= 2:
        single, average = icc2([[float(v) for v in row] for row in rows])
        result["overall"].update(icc_single=single, icc_average=average, n=len(rows))
    human_overall = {}
    for s in sessions:
        levels = [overall_level(dump.ratings[r][s]) for r in raters if s in dump.ratings[r]]
        levels = [v for v in levels if v is not None]
        if levels:
            human_overall[s] = statistics.mean(levels)
    paired = [s for s in human_overall if s in dump.engine and dump.engine[s].get("overall") is not None]
    if len(paired) >= 3:
        result["overall"]["engine_spearman"] = spearman([dump.engine[s]["overall"] for s in paired],
                                                        [human_overall[s] for s in paired])
        result["overall"]["engine_n"] = len(paired)
    result["overall"]["intended"] = _intended_overall(dump, human_overall)

    unclear = []
    for axis in AXES:
        stats = {}
        per_rater = {r: [_level(dump.ratings[r][s]["axes"].get(axis)) for s in complete] for r in raters}
        if len(raters) >= 2 and complete:
            stats.update(mean_pairwise_kappa(per_rater))
        human = {s: [_level(dump.ratings[r][s]["axes"].get(axis)) for r in raters if s in dump.ratings[r]]
                 for s in sessions}
        human = {s: v for s, v in human.items() if v}
        scored = [s for s, v in human.items() if not _majority_na(v)
                  and s in dump.engine and dump.engine[s]["axes"].get(axis) is not None]
        if len(scored) >= 3:
            stats["engine_spearman"] = spearman(
                [dump.engine[s]["axes"][axis] for s in scored],
                [statistics.mean(x for x in human[s] if x is not None) for s in scored])
            stats["engine_n"] = len(scored)
        both = [s for s in human if s in dump.engine]
        if both:
            stats["engine_na_agreement"] = sum(
                (dump.engine[s]["axes"].get(axis) is None) == _majority_na(human[s]) for s in both) / len(both)
        stats.update(_intended_axis(dump, human, axis))
        kappa = stats.get("kappa")
        if kappa is None or (isinstance(kappa, float) and math.isnan(kappa)) or kappa < KAPPA_TARGET:
            unclear.append(axis)
        result["axes"][axis] = stats
    result["unclear_axes"] = unclear
    return result


def _intended_axis(dump: Dump, human: dict[str, list[int | None]], axis: str) -> dict:
    pairs = []
    for s, levels in human.items():
        planned = dump.intended.get(s, {}).get(axis)
        if planned is None or planned == "after-run":
            continue
        observed = "NA" if _majority_na(levels) else round(statistics.median(x for x in levels if x is not None))
        pairs.append((planned, observed))
    if not pairs:
        return {}
    numeric = [(a, b) for a, b in pairs if isinstance(a, int) and isinstance(b, int)]
    return {
        "intended_exact": sum(a == b for a, b in pairs) / len(pairs),
        "intended_mad": statistics.mean(abs(a - b) for a, b in numeric) if numeric else None,
        "intended_n": len(pairs),
    }


def _intended_overall(dump: Dump, human_overall: dict[str, float]) -> dict:
    pairs = [(OVERALL_LEVELS.index(dump.intended[s]["overall"]), round(v)) for s, v in human_overall.items()
             if dump.intended.get(s, {}).get("overall") in OVERALL_LEVELS]
    if not pairs:
        return {}
    return {"exact": sum(a == b for a, b in pairs) / len(pairs),
            "mad": statistics.mean(abs(a - b) for a, b in pairs), "n": len(pairs)}


# ---------- Markdown ----------

def _f(value: object, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def _pct(value: object) -> str:
    return "—" if value is None else f"{100 * value:.0f}%"


def render(result: dict) -> str:
    c = result["counts"]
    out = ["# Kết quả hiệu chuẩn (P1.3)", "",
           f"- Người chấm: {c['raters']} · Lượt làm bài: {c['sessions']} · Lượt được tất cả chấm: {c['complete']}"]
    if result["missing"]:
        out.append("- Còn thiếu: " + ", ".join(f"{r} thiếu {n} lượt" for r, n in result["missing"].items()))
    out += ["", "## AHP: trọng số các trục", "", "| Thành viên | CR | " + " | ".join(AXIS_NAMES[a] for a in AXES) + " |",
            "|---|---|" + "---|" * len(AXES)]
    for rater, m in result["ahp"]["members"].items():
        if "error" in m:
            out.append(f"| {rater} | lỗi: {m['error']} |" + " |" * len(AXES))
            continue
        flag = " ⚠" if m["cr"] >= ahp.CR_THRESHOLD else ""
        out.append(f"| {rater} | {_f(m['cr'], 3)}{flag} | " + " | ".join(_pct(m["weights"][a]) for a in AXES) + " |")
    rows = [("Nhóm (AIJ, mọi người)", result["ahp"]["group_weights"]),
            ("Nhóm (chỉ CR < 0,1)", result["ahp"]["group_consistent_weights"]),
            ("Trọng số hiện tại", result["ahp"]["current_weights"]),
            ("Trọng số đều nhau", result["ahp"]["equal_weights"])]
    for label, weights in rows:
        if weights:
            out.append(f"| **{label}** | | " + " | ".join(_pct(weights[a]) for a in AXES) + " |")

    o = result["overall"]
    out += ["", "## Mức tổng thể", "",
            f"- ICC(2,1) giữa người chấm: {_f(o.get('icc_single'))} · ICC(2,k): {_f(o.get('icc_average'))}"
            f" (n = {o.get('n', 0)})",
            f"- Spearman điểm engine vs trung bình người chấm: {_f(o.get('engine_spearman'))}"
            f" (n = {o.get('engine_n', 0)})"]
    if o.get("intended"):
        out.append(f"- Khớp mức dự kiến của kịch bản: {_pct(o['intended']['exact'])}, lệch trung bình "
                   f"{_f(o['intended']['mad'])} mức (n = {o['intended']['n']})")

    out += ["", "## Từng trục", "",
            "| Trục | κ giữa người chấm | Đồng ý N/A | Spearman engine | Engine–người đồng ý N/A | Khớp dự kiến |",
            "|---|---|---|---|---|---|"]
    for axis in AXES:
        s = result["axes"][axis]
        out.append(f"| {AXIS_NAMES[axis]} | {_f(s.get('kappa'))} | {_pct(s.get('na_agreement'))} | "
                   f"{_f(s.get('engine_spearman'))} (n = {s.get('engine_n', 0)}) | "
                   f"{_pct(s.get('engine_na_agreement'))} | {_pct(s.get('intended_exact'))} |")
    if result["unclear_axes"]:
        out += ["", "Trục có κ < 0,6 (bảng mức điểm chưa đủ rõ, cần sửa ở P1.4): "
                + ", ".join(AXIS_NAMES[a] for a in result["unclear_axes"]) + "."]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(render(analyse(load_dump(args.data))), encoding="utf-8")
    print(f"written {args.out}")


if __name__ == "__main__":
    main()
