"""Testing and Debugging (rubric v2), with regressions from the P1.3 golden set."""
from app.features.scoring.evidence import Evidence
from app.features.scoring import rubric

debugging = rubric.debugging
score_testing = rubric.testing

MIN = 60_000


def run(minute: float, ratio: float, starter: bool = False) -> dict:
    return {"type": "RUN", "ts": int(minute * MIN), "integrity_flags": [],
            "payload": {"passed": ratio == 1.0, "passRatio": ratio, "isStarter": starter}}


def suite(passed: int, total: int, visible_passed: int, visible_total: int = 2) -> dict:
    return {"type": "SUBMIT_TESTS", "ts": 30 * MIN, "integrity_flags": [],
            "payload": {"passed": passed, "total": total, "visiblePassed": visible_passed,
                        "visibleTotal": visible_total, "passRatio": round(passed / total, 3)}}


def ev(*events: dict, kind: str = "implement") -> Evidence:
    return Evidence(exercise_kind=kind, events=sorted(events, key=lambda e: e["ts"]))


# ---------- Testing ----------

def test_score_testings_follow_the_submit_suite():
    assert score_testing(ev(run(3, 1.0), suite(8, 8, 2))).level == 3
    assert score_testing(ev(run(3, 1.0), suite(4, 8, 2))).level == 2   # visible pass, hidden fail
    assert score_testing(ev(run(3, 1.0), suite(3, 8, 2))).level == 2   # sim-11: few pass, but all visible do
    assert score_testing(ev(run(3, 0.5), suite(5, 8, 1))).level == 1   # submitted with a visible test failing
    assert score_testing(ev(run(3, 0.0), suite(1, 8, 0))).level == 0   # submitted failing nearly all


def test_never_running_is_level_0_unless_everything_passes():
    assert score_testing(ev(suite(0, 7, 0))).level == 0                # sim-15: submitted at once
    assert score_testing(ev(suite(3, 8, 1))).level == 0
    assert score_testing(ev()).level == 0


def test_sessions_without_a_submit_suite_use_the_last_run():
    # Before P1.2 there was no full suite at submit; hidden tests are unknown, so at most 2.
    assert score_testing(ev(run(2, 0.5), run(4, 1.0))).level == 2
    assert score_testing(ev(run(2, 1.0), run(4, 0.5))).level == 1
    assert score_testing(ev(run(2, 0.0))).level == 0


# ---------- Debugging ----------

def test_implement_without_a_real_failing_run_is_not_applicable():
    out = debugging(ev(run(1, 0.0, starter=True), run(3, 1.0), suite(8, 8, 2)))
    assert out.level is None and out.reason == "no_failure"


def test_debug_exercises_are_never_not_applicable():
    out = debugging(ev(suite(7, 7, 2), kind="debug"))
    assert out.level == 3  # fixed with no failing run at all


def test_an_unfixed_debug_exercise_is_level_0_even_if_the_visible_tests_pass():
    # sim-19 / sim-24 / sim-28: the buggy code passes the visible tests, the bug stays,
    # v1 gave 20/20 because nothing ever failed.
    out = debugging(ev(run(2, 1.0, starter=True), run(4, 1.0), suite(4, 7, 2), kind="debug"))
    assert out.level == 0 and out.reason == "not_fixed"


def test_fixed_levels_count_the_failing_runs():
    fixed = suite(8, 8, 2)
    assert debugging(ev(run(2, 0.5), run(4, 1.0), fixed)).level == 3
    assert debugging(ev(run(2, 0.5), run(3, 0.0), run(4, 1.0), fixed)).level == 2
    assert debugging(ev(*[run(m, 0.5) for m in (1, 2, 3, 4)], run(5, 1.0), fixed)).level == 1


def test_an_implement_failure_never_fixed_is_level_0():
    # sim-08: three failing attempts, submitted failing.
    assert debugging(ev(run(2, 0.0), run(3, 0.0), run(4, 0.5), suite(1, 8, 0))).level == 0


def test_starter_runs_are_not_failures():
    out = debugging(ev(run(1, 0.0, starter=True), run(2, 0.0, starter=True), run(4, 1.0), suite(7, 7, 2),
                       kind="debug"))
    assert out.level == 3
