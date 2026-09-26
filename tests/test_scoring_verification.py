"""Verification (rubric v2), with regressions from the P1.3 golden set."""
from app.features.scoring.evidence import Evidence, Reply, Snapshot
from app.features.scoring.rubric import verification

MIN = 60_000
STARTER = "def two_sum(nums, target):\n    pass"
AI_TWO_SUM = ("def two_sum(nums, target):\n    num_to_index = {}\n    for index, num in enumerate(nums):\n"
              "        complement = target - num\n        if complement in num_to_index:\n"
              "            return [num_to_index[complement], index]\n        num_to_index[num] = index")


def reply(minute: float, code: str | None, prompt: str = "help") -> Reply:
    text = f"Try this:\n```python\n{code}\n```" if code else "Think about a dict."
    return Reply(prompt=prompt, text=text, at_ms=int(minute * MIN), injected=False)


def snap(minute: float, code: str, version: int) -> Snapshot:
    return Snapshot(version=version, code=code, at_ms=int(minute * MIN))


def evidence(replies, snapshots, passed: bool | None = True, prompt_flags=None) -> Evidence:
    events = [{"type": "PROMPT", "ts": r.at_ms - 1, "payload": {}, "integrity_flags": []} for r in replies]
    if passed is not None:
        events.append({"type": "SUBMIT_TESTS", "ts": 30 * MIN, "integrity_flags": [],
                       "payload": {"passed": 8 if passed else 3, "total": 8}})
    if prompt_flags is not None:
        events.append({"type": "JUDGE", "ts": 31 * MIN, "integrity_flags": [],
                       "payload": {"kind": "prompts", "levels": [2] * len(replies),
                                   "questions_ai_code": prompt_flags}})
    events.sort(key=lambda e: e["ts"])
    return Evidence(exercise_kind="implement", events=events, replies=list(replies), snapshots=list(snapshots))


def test_not_applicable_when_ciel_gave_no_code():
    # sim-09 / sim-27: a trap exercise whose reply had no code block.
    out = verification(evidence([reply(3, None)], [snap(1, STARTER, 1)]))
    assert out.level is None and out.reason == "no_ai_code"


def test_pasted_unchanged_and_passing_is_level_1():
    # sim-02: begged for the code, pasted Ciel's function as is, it passed.
    out = verification(evidence([reply(1, AI_TWO_SUM)], [snap(0, STARTER, 1), snap(2, AI_TWO_SUM, 2)]))
    assert out.level == 1 and out.reason == "pasted_unchanged"


def test_pasted_unchanged_and_failing_is_level_0():
    # sim-18: pasted the AI code, tests failed, submitted anyway.
    out = verification(evidence([reply(1, AI_TWO_SUM)], [snap(0, STARTER, 1), snap(2, AI_TWO_SUM, 2)], passed=False))
    assert out.level == 0


def test_pasted_then_fixed_is_level_3_and_still_failing_is_2():
    fixed = AI_TWO_SUM.replace("num_to_index[num] = index", "num_to_index[num] = index\n    return []") \
                      .replace("complement = target - num", "complement = target - num  # checked")
    snaps = [snap(0, STARTER, 1), snap(2, AI_TWO_SUM, 2), snap(4, fixed, 3)]
    assert verification(evidence([reply(1, AI_TWO_SUM)], snaps)).level == 3
    assert verification(evidence([reply(1, AI_TWO_SUM)], snaps, passed=False)).level == 2


def test_ai_code_not_used_is_level_2():
    # sim-16 / sim-20 / sim-26: Ciel showed code, the student kept their own.
    own = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        pass"
    out = verification(evidence([reply(1, AI_TWO_SUM)], [snap(0, own, 1), snap(2, own + "\n    return []", 2)]))
    assert out.level == 2 and out.reason == "not_used"


def test_questioning_unused_ai_code_is_level_3():
    out = verification(evidence([reply(1, AI_TWO_SUM), reply(5, None, prompt="is your code right?")],
                                [snap(0, STARTER, 1)], prompt_flags=[False, True]))
    assert out.level == 3 and out.reason == "questioned"


def test_questions_before_the_code_do_not_count():
    out = verification(evidence([reply(1, None, prompt="is this right?"), reply(5, AI_TWO_SUM)],
                                [snap(0, STARTER, 1)], prompt_flags=[True, False]))
    assert out.level == 2


def test_lines_the_student_already_had_are_not_pasting():
    # sim-06: Ciel's snippet repeats lines of the buggy starter the student already had.
    starter = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
    ai = "def sum_first_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
    out = verification(evidence([reply(1, ai)], [snap(0, starter, 1), snap(3, starter.replace("+=", "="), 2)],
                                passed=False))
    assert out.level == 2 and out.reason == "not_used"


def test_sessions_without_a_submit_suite_use_the_last_run():
    # Before P1.2 there was no full suite at submit (attempts 44 / 46 in the production dry run
    # dropped to 0 because "no suite" was read as "failing").
    ev = evidence([reply(1, AI_TWO_SUM)], [snap(0, STARTER, 1), snap(2, AI_TWO_SUM, 2)], passed=None)
    ev.events.append({"type": "RUN", "ts": 3 * MIN, "integrity_flags": [],
                      "payload": {"passed": True, "passRatio": 1.0, "isStarter": False}})
    assert verification(ev).level == 1
    ev.events.append({"type": "RUN", "ts": 4 * MIN, "integrity_flags": [],
                      "payload": {"passed": False, "passRatio": 0.5, "isStarter": False}})
    assert verification(ev).level == 0


def test_the_worst_handled_reply_counts():
    own = "def two_sum(nums, target):\n    return []"
    snaps = [snap(0, STARTER, 1), snap(2, AI_TWO_SUM, 2)]
    out = verification(evidence([reply(1, AI_TWO_SUM), reply(3, "x = compute(own)\ny = x + 1\nz = y * 2")], snaps,
                                passed=False))
    assert out.level == 0  # pasted and failing beats the unused second snippet
    assert verification(evidence([reply(1, "a = 1\nb = 2\nc = 3")], [snap(0, own, 1)])).level == 2
