import json
import math

import pytest

from app.features.calibration.ahp import AXES, PAIRS
from app.features.calibration.analyze import OVERALL_LEVELS, analyse, load_dump, render


def _ahp_doc(weights: dict[str, float]) -> dict:
    """A perfectly consistent AHP answer set derived from known weights."""
    answers = {f"{a}|{b}": weights[a] / weights[b] for a, b in PAIRS}
    return {"answers": answers, "cr": 0.0, "saved_at": "2026-09-30T10:00:00Z"}


def _rating(sid: str, level: int | None, overall: str) -> dict:
    return {"session_id": sid, "axes": {a: level for a in AXES}, "overall": overall, "note": ""}


def _write(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _dump(tmp_path):
    w = {"understanding": 0.3, "hypothesis": 0.25, "prompting": 0.15, "verification": 0.15, "testing": 0.1,
         "debugging": 0.05}
    _write(tmp_path / "ahp" / "u_a.json", _ahp_doc(w))
    # ArtifactData dumps may wrap the body: {"id", "data", "version"}.
    _write(tmp_path / "ahp" / "u_b.json", {"id": "u_b", "data": _ahp_doc(w), "version": 3})
    sessions = ["S1", "S2", "S3", "S4"]
    levels = {"S1": 0, "S2": 1, "S3": 2, "S4": 3}
    for rater in ("u_a", "u_b", "u_c"):
        for sid in sessions:
            _write(tmp_path / "ratings" / rater / "items" / f"{sid}.json",
                   _rating(sid, levels[sid], OVERALL_LEVELS[levels[sid]]))
    # u_c's own summary doc sits beside its items folder and must be ignored.
    _write(tmp_path / "ratings" / "u_c.json", {"count": 4})
    engine = {sid: {"overall": 20.0 * (levels[sid] + 1), "axes": {a: 5.0 * (levels[sid] + 1) for a in AXES}}
              for sid in sessions}
    engine["S1"]["axes"]["debugging"] = None
    _write(tmp_path / "engine.json", engine)
    _write(tmp_path / "keys.json", {"S1": 11, "S2": 12, "S3": 13, "S4": 14})
    _write(tmp_path / "state.json", {"sessions": {f"sim-0{i}": {"attempt_id": 10 + i} for i in range(1, 5)}})
    _write(tmp_path / "profiles.json", {f"sim-0{i}": {**{a: i - 1 for a in AXES}, "overall": OVERALL_LEVELS[i - 1]}
                                        for i in range(1, 5)})
    return w


def test_load_dump_reads_raters_and_unwraps_documents(tmp_path):
    _dump(tmp_path)
    data = load_dump(tmp_path)
    assert set(data.ahp) == {"u_a", "u_b"}
    assert set(data.ratings) == {"u_a", "u_b", "u_c"}
    assert set(data.ratings["u_c"]) == {"S1", "S2", "S3", "S4"}
    assert data.intended["S3"]["testing"] == 2


def test_perfect_agreement_and_known_weights(tmp_path):
    w = _dump(tmp_path)
    result = analyse(load_dump(tmp_path))
    group = result["ahp"]["group_weights"]
    assert all(math.isclose(group[a], w[a], abs_tol=1e-6) for a in AXES)
    assert all(m["cr"] < 1e-9 for m in result["ahp"]["members"].values())
    assert math.isclose(result["overall"]["icc_single"], 1.0)
    assert all(math.isclose(result["axes"][a]["kappa"], 1.0) for a in AXES)
    # Engine rises with the human levels, so rank agreement is perfect.
    assert math.isclose(result["axes"]["testing"]["engine_spearman"], 1.0)
    assert math.isclose(result["overall"]["engine_spearman"], 1.0)
    assert result["axes"]["testing"]["intended_exact"] == 1.0
    assert result["counts"] == {"raters": 3, "sessions": 4, "complete": 4}


def test_partial_ratings_are_reported_not_fatal(tmp_path):
    _dump(tmp_path)
    (tmp_path / "ratings" / "u_c" / "items" / "S4.json").unlink()
    result = analyse(load_dump(tmp_path))
    assert result["counts"]["complete"] == 3
    assert result["missing"] == {"u_c": 1}
    text = render(result)
    assert "u_c" in text and "ICC" in text and "AHP" in text


def test_rating_page_exports_are_read_and_the_latest_one_wins(tmp_path):
    w = _dump(tmp_path)
    export_dir = tmp_path / "exports"
    old = {"format": "codeprove-calibration/v1", "rater": "Trung", "exported_at": "2026-09-26T10:00:00Z",
           "ahp": None, "ratings": {"S1": _rating("S1", 0, "emerging")}}
    new = {**old, "exported_at": "2026-09-27T10:00:00Z", "ahp": _ahp_doc(w),
           "ratings": {s: _rating(s, lv, OVERALL_LEVELS[lv]) for s, lv in (("S1", 0), ("S2", 1))}}
    export_dir.mkdir()
    (export_dir / "trung-1.txt").write_text(json.dumps(old), encoding="utf-8")
    # Pasted from Zalo with stray text around the JSON.
    (export_dir / "trung-2.txt").write_text("Trung gửi:\n" + json.dumps(new) + "\n", encoding="utf-8")
    data = load_dump(tmp_path)
    assert set(data.ratings["Trung"]) == {"S1", "S2"}
    assert "Trung" in data.ahp
    result = analyse(data)
    assert result["missing"]["Trung"] == 2


def test_a_file_that_is_not_an_export_is_rejected(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "x.json").write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="x.json"):
        load_dump(tmp_path)


def test_disagreement_flags_an_unclear_axis(tmp_path):
    _dump(tmp_path)
    for sid, level in {"S1": 3, "S2": 0, "S3": 3, "S4": 0}.items():
        path = tmp_path / "ratings" / "u_c" / "items" / f"{sid}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["axes"]["prompting"] = level
        path.write_text(json.dumps(doc), encoding="utf-8")
    result = analyse(load_dump(tmp_path))
    assert result["axes"]["prompting"]["kappa"] < 0.6
    assert "prompting" in result["unclear_axes"]
