import asyncio

from app.features.feedback.diagnosis import Finding
from app.features.feedback.templates import render
from app.features.feedback.writer import MAX_FIELD_CHARS, write_feedback

FINDINGS = [
    Finding(code="explain_shallow", axis="understanding", kind="risk", severity="medium",
            evidence="vòng lặp chạy từ 1 tới n"),
    Finding(code="hypothesis_strong", axis="hypothesis", kind="strength", evidence="dict lưu phần bù, O(n)"),
]
TESTING = Finding(code="explain_shallow", axis="testing", kind="risk", severity="medium",
                  params={"failed_categories": ["edge"]}, evidence="5/8")
CANDIDATES = ["CP-105", "CP-003"]
SPECIFIC = {
    "explain_shallow": "Bạn trả lời \"vòng lặp chạy từ 1 tới n\" nhưng chưa nói vì sao dừng ở n.",
    "hypothesis_strong": "Bạn ghi ngay từ đầu: dict lưu phần bù, O(n), và cẩn thận với [3, 3].",
}


def item(code, line=None):
    return {"code": code, "what_happened": SPECIFIC.get(code, "Bạn đã làm X.") if line is None else line}


class Fake:
    _model = "fake"

    def __init__(self, reply=None, delay=0.0, error=None):
        self.reply, self.delay, self.error, self.calls = reply, delay, error, []

    async def judge(self, system, user, max_tokens=300):
        self.calls.append((system, user, max_tokens))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply


async def write(client, findings=FINDINGS, timeout=12.0, candidates=CANDIDATES):
    return await write_feedback(client, locale="vi", problem="Two-sum", findings=findings,
                                final_code="def f():\n    return 1", answers=[{"question": "Why?", "answer": "Vì."}],
                                candidates=candidates, timeout=timeout)


def template(finding, next_exercise="CP-105"):
    return render(finding, "vi", next_exercise)


async def test_the_llm_writes_what_happened_and_the_advice_stays_reviewed():
    client = Fake({"items": [item("hypothesis_strong"), item("explain_shallow")]})
    out = await write(client)
    assert [x["code"] for x in out] == ["explain_shallow", "hypothesis_strong"]
    assert all(x["source"] == "llm" and "fallback_reason" not in x for x in out)
    assert out[0]["text"]["what_happened"] == SPECIFIC["explain_shallow"]
    for field in ("why_it_matters", "how_to_improve", "try_next"):
        assert out[0]["text"][field] == template(FINDINGS[0])[field]
    assert out[0]["next_exercise"] == "CP-105" and out[0]["severity"] == "medium"
    prompt = client.calls[0][1]
    assert "explain_shallow" in prompt and "Vì." in prompt
    # The generic line goes along so the writer knows what NOT to repeat.
    assert template(FINDINGS[0])["what_happened"] in prompt


async def test_a_copy_of_the_template_line_is_not_counted_as_written():
    copied = item("explain_shallow", template(FINDINGS[0])["what_happened"].upper())
    out = await write(Fake({"items": [copied, item("hypothesis_strong")]}))
    assert out[0]["source"] == "template" and out[0]["fallback_reason"] == "copied_template"


async def test_long_code_is_stripped_and_code_only_lines_rejected():
    leak = "Bạn viết:\n```python\ndef two_sum(n, t):\n    seen = {}\n    return []\n```"
    out = await write(Fake({"items": [item("explain_shallow", leak), item("hypothesis_strong")]}))
    assert out[0]["source"] == "llm" and "def two_sum" not in out[0]["text"]["what_happened"]
    code_only = "```python\na = 1\nb = 2\nc = 3\n```"
    out = await write(Fake({"items": [item("explain_shallow", code_only), item("hypothesis_strong")]}))
    assert out[0]["fallback_reason"] == "empty_field:what_happened"


async def test_lines_suggesting_an_exercise_or_too_long_are_rejected():
    out = await write(Fake({"items": [item("explain_shallow", "Bạn nên làm bài CP-208."),
                                      item("hypothesis_strong", "x" * (MAX_FIELD_CHARS + 1))]}))
    assert [x["fallback_reason"] for x in out] == ["exercise_mentioned", "too_long:what_happened"]


async def test_each_template_line_records_why_it_was_kept():
    assert (await write(Fake({"items": [item("explain_shallow")]})))[1]["fallback_reason"] == "no_item"
    assert (await write(Fake({})))[0]["fallback_reason"] == "invalid_json"  # e.g. truncated JSON
    assert (await write(Fake({"items": []}, delay=0.5), timeout=0.05))[0]["fallback_reason"] == "timeout"
    assert (await write(Fake(error=RuntimeError("down"))))[0]["fallback_reason"] == "call_failed"


async def test_a_failed_call_keeps_the_whole_template():
    out = await write(Fake(error=RuntimeError("down")))
    assert [x["source"] for x in out] == ["template", "template"]
    assert out[0]["text"] == template(FINDINGS[0])


async def test_without_candidates_no_exercise_is_suggested():
    out = await write(Fake({"items": [item("explain_shallow"), item("hypothesis_strong")]}), candidates=[])
    assert out[0]["next_exercise"] is None and "CP-" not in out[0]["text"]["try_next"]


async def test_no_findings_means_no_call():
    client = Fake({"items": []})
    assert await write(client, findings=[]) == []
    assert client.calls == []


async def test_count_based_findings_keep_their_exact_template_line():
    # Round 3 misread test counts ("6/7 visible", "4/7 fail"): these lines stay templated.
    client = Fake({"items": [item("explain_shallow"), {"code": "hidden_edge_failed", "what_happened": "6/7 visible"}]})
    out = await write(client, findings=[FINDINGS[0], TESTING])
    assert out[1]["source"] == "template" and "fallback_reason" not in out[1]
    assert out[1]["text"] == template(TESTING)
    assert "hidden_edge_failed" not in client.calls[0][1]
    only_counts = Fake({"items": []})
    assert (await write(only_counts, findings=[TESTING]))[0]["source"] == "template"
    assert only_counts.calls == []
