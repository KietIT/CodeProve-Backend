import asyncio

from app.features.feedback.diagnosis import Finding
from app.features.feedback.templates import render
from app.features.feedback.writer import MAX_FIELD_CHARS, write_feedback

FINDINGS = [
    Finding(code="hidden_edge_failed", axis="testing", kind="risk", severity="medium",
            params={"failed_categories": ["edge"]}, evidence="5/8"),
    Finding(code="explain_strong", axis="understanding", kind="strength", evidence="vì dict tra O(1)"),
]
CANDIDATES = ["CP-105", "CP-003"]


def item(code, **overrides):
    base = {"code": code, "what_happened": f"{code}: bạn đã làm X.", "why_it_matters": "Vì Y.",
            "how_to_improve": "Hãy làm Z.", "try_next": "Thử bài CP-105.", "next_exercise": "CP-105"}
    return {**base, **overrides}


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


async def write(client, findings=FINDINGS, timeout=12.0):
    return await write_feedback(client, locale="vi", problem="Two-sum", findings=findings,
                                final_code="def f():\n    return 1", answers=[{"question": "Why?", "answer": "Vì."}],
                                candidates=CANDIDATES, timeout=timeout)


def template(finding, next_exercise="CP-105"):
    return render(finding, "vi", next_exercise)


async def test_valid_items_are_used_in_finding_order():
    client = Fake({"items": [item("explain_strong"), item("hidden_edge_failed")]})
    out = await write(client)
    assert [x["code"] for x in out] == ["hidden_edge_failed", "explain_strong"]
    assert all(x["source"] == "llm" for x in out)
    assert out[0]["text"]["what_happened"] == "hidden_edge_failed: bạn đã làm X."
    assert out[0]["next_exercise"] == "CP-105" and out[0]["severity"] == "medium"
    prompt = client.calls[0][1]
    assert "hidden_edge_failed" in prompt and "CP-105" in prompt and "Vì." in prompt


async def test_a_finding_without_a_valid_item_falls_back_to_its_template():
    out = await write(Fake({"items": [item("hidden_edge_failed"), item("made_up_code")]}))
    assert out[0]["source"] == "llm"
    assert out[1]["source"] == "template" and out[1]["text"] == template(FINDINGS[1])


async def test_long_code_blocks_are_stripped_and_code_only_fields_rejected():
    leak = "Sửa thế này:\n```python\ndef two_sum(n, t):\n    seen = {}\n    return []\n```"
    out = await write(Fake({"items": [item("hidden_edge_failed", how_to_improve=leak), item("explain_strong")]}))
    assert out[0]["source"] == "llm" and "```" not in out[0]["text"]["how_to_improve"]
    assert "def two_sum" not in out[0]["text"]["how_to_improve"]
    code_only = "```python\na = 1\nb = 2\nc = 3\n```"
    out = await write(Fake({"items": [item("hidden_edge_failed", why_it_matters=code_only), item("explain_strong")]}))
    assert out[0]["source"] == "template"


async def test_a_suggestion_outside_the_candidates_falls_back():
    bad = item("hidden_edge_failed", next_exercise="CP-999", try_next="Thử bài CP-999.")
    out = await write(Fake({"items": [bad, item("explain_strong")]}))
    assert out[0]["source"] == "template" and out[1]["source"] == "llm"
    sneaky = item("hidden_edge_failed", next_exercise="", try_next="Thử bài CP-208.")
    assert (await write(Fake({"items": [sneaky, item("explain_strong")]})))[0]["source"] == "template"


async def test_empty_or_too_long_fields_fall_back():
    out = await write(Fake({"items": [item("hidden_edge_failed", why_it_matters="  "),
                                      item("explain_strong", what_happened="x" * (MAX_FIELD_CHARS + 1))]}))
    assert [x["source"] for x in out] == ["template", "template"]


async def test_a_failed_or_slow_call_uses_templates_for_everything():
    for client, timeout in ((Fake(error=RuntimeError("down")), 12.0), (Fake({"items": []}, delay=0.5), 0.05)):
        out = await write(client, timeout=timeout)
        assert [x["source"] for x in out] == ["template", "template"]
        assert out[0]["text"] == template(FINDINGS[0])


async def test_no_findings_means_no_call():
    client = Fake({"items": []})
    assert await write(client, findings=[]) == []
    assert client.calls == []
