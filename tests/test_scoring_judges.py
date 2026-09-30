import pytest

from app.features.scoring.judges import judge_explain, judge_hypothesis, judge_locate, judge_prompts, level_of

STARTER = "def f(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"


class Scripted:
    """Fake LLM client returning canned verdicts and recording the calls."""

    _model = "fake"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    async def judge(self, system, user, max_tokens=300):
        self.calls.append((system, user, max_tokens))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_level_of_accepts_only_0_to_3():
    assert [level_of(v) for v in (0, 3, "2", 1.0, 2.5, 4, -1, None, "x", True)] == \
        [0, 3, 2, 1, None, None, None, None, None, None]


async def test_prompts_are_judged_in_one_call_and_matched_by_number():
    client = Scripted({"prompts": [
        {"i": 2, "level": 3, "evidence": "mình dùng range(1, n)", "questions_ai_code": True},
        {"i": 1, "level": 0, "evidence": "viết code", "asks_for_solution": True},
    ]})
    out = await judge_prompts(client, "Sum 1..n", ["viết code cho tôi", "mình dùng range(1, n) thì sai", "ok"])
    assert len(client.calls) == 1 and "3. ok" in client.calls[0][1]
    assert [p["level"] for p in out] == [0, 3, None]  # message 3 got no verdict: N/A, not invented
    assert out[0]["asks_for_solution"] is True and out[1]["questions_ai_code"] is True
    assert out[2] == {"level": None, "evidence": "", "asks_for_solution": False, "questions_ai_code": False}


async def test_prompt_judge_failure_leaves_every_prompt_unrated():
    out = await judge_prompts(Scripted(TimeoutError()), "p", ["a", "b"])
    assert [p["level"] for p in out] == [None, None]
    assert await judge_prompts(Scripted(), "p", []) == []


async def test_explain_returns_the_v1_score_and_the_level():
    client = Scripted({"score": 16, "reason": "ok", "level": 3, "evidence": "vì range dừng trước n"})
    out = await judge_explain(client, "Why?", "range(1, n + 1) vì range dừng trước n, n = 0 thì trả 0")
    assert out == {"score": 16.0, "level": 3, "evidence": "vì range dừng trước n"}


async def test_explain_short_answers_are_level_0_without_a_call():
    client = Scripted()
    assert await judge_explain(client, "Why?", "idk") == {"score": 0.0, "level": 0, "evidence": ""}
    assert client.calls == []


async def test_explain_without_a_level_keeps_the_score_and_marks_the_level_unknown():
    out = await judge_explain(Scripted({"score": 25, "reason": "?"}), "Why?", "because the loop adds every number")
    assert out == {"score": 20.0, "level": None, "evidence": ""}


async def test_hypothesis_keeps_the_verdict_and_adds_the_level():
    client = Scripted({"correct": True, "note": "Đúng hướng.", "level": 2, "evidence": "dict lưu số đã gặp"})
    out = await judge_hypothesis(client, "Two-sum", "dict lưu số đã gặp")
    assert out == {"correct": True, "note": "Đúng hướng.", "level": 2, "evidence": "dict lưu số đã gặp"}


async def test_hypothesis_errors_still_propagate():
    # Same as before P1.4: the caller sees the failure instead of a silent "wrong".
    with pytest.raises(TimeoutError):
        await judge_hypothesis(Scripted(TimeoutError()), "p", "text")


async def test_the_explain_judge_sees_the_code_and_the_test_results_when_given():
    client = Scripted({"score": 5, "level": 1, "evidence": "lock makes it safe"})
    context = "Student's final code:\n...\nTest results at submit: 6/7 passed"
    await judge_explain(client, "Why the lock?", "the lock makes it thread safe here", context)
    system, user, _ = client.calls[0]
    assert user.startswith(context) and user.endswith("Answer: the lock makes it thread safe here")
    # P2.5: presenting code the tests show wrong as correct caps the level.
    assert "at most level 1" in system


async def test_locate_reason_is_judged_against_the_real_bug_with_numbered_code():
    client = Scripted({"level": 3, "evidence": "stops before n"})
    verdict = await judge_locate(client, STARTER, "Line 3: range(1, n) never adds n.", [3],
                                 "range(1, n) stops before n so n is never added")
    assert verdict == {"level": 3, "evidence": "stops before n"}
    system, user, _ = client.calls[0]
    assert "3 |     for i in range(1, n):" in user  # the judge sees what the student saw, numbered
    assert "Selected lines: 3" in user and "Line 3: range(1, n) never adds n." in user


async def test_an_empty_or_trivial_reason_is_level_0_without_a_call():
    client = Scripted()
    assert await judge_locate(client, STARTER, "x", [3], "") == {"level": 0, "evidence": ""}
    assert await judge_locate(client, STARTER, "x", [3], "sai") == {"level": 0, "evidence": ""}
    assert client.calls == []


async def test_a_failed_locate_judge_leaves_the_reason_unrated():
    client = Scripted(RuntimeError("down"))
    assert await judge_locate(client, STARTER, "x", [3], "the loop bound is off by one") == {
        "level": None, "evidence": ""}


def test_explain_context_names_the_code_and_the_failing_tests_but_no_inputs():
    from app.features.attempts.scoring_service import explain_context

    suite = {"passed": 6, "total": 7, "failures": [
        {"description": "increment waits while another thread holds the lock", "input": "SECRET", "hidden": True}]}
    context = explain_context("def inc():\n    with threading.Lock():\n        x += 1", suite)
    assert "with threading.Lock():" in context and "6/7 passed" in context
    assert "increment waits while another thread holds the lock" in context and "SECRET" not in context
    assert explain_context("", suite) == "" and explain_context(None, None) == ""
    assert "Test results" not in explain_context("x = 1", None)


def test_the_question_generator_asks_only_about_the_code():
    from app.features.mentor.prompts import EXPLAIN_QUESTION_SYSTEM
    assert "does not appear in the code" in EXPLAIN_QUESTION_SYSTEM
