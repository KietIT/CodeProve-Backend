import json

from sqlalchemy import func, select

from app.features.feedback.preview import check, guess_locale, preview_all
from app.features.scoring.evidence import Evidence
from tests.test_scoring_backfill import FakeJudge, _scored_attempt

REFERENCE = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        return [seen[target - n], i]"


def entry(code="hidden_edge_failed", next_exercise="CP-105", **text):
    fields = {"what_happened": "Bạn đã làm X.", "why_it_matters": "Vì Y.", "how_to_improve": "Hãy làm Z.",
              "try_next": "Thử bài CP-105.", **text}
    return {"code": code, "text": fields, "next_exercise": next_exercise, "source": "llm"}


def preview(*entries, final_code="def two_sum(nums, target):\n    return []"):
    return {"S1": {"exercise": "CP-001", "final_code": final_code, "candidates": ["CP-105"],
                   "diagnosis_codes": [e["code"] for e in entries], "findings": list(entries)}}


def test_guess_locale_from_the_explain_back_questions():
    ev = lambda q: Evidence(exercise_kind="implement", answers=[{"question": q, "answer": ""}])  # noqa: E731
    assert guess_locale(ev("Bạn có thể giải thích vì sao dùng dict không?")) == "vi"
    assert guess_locale(ev("Why did you use a dict?")) == "en"
    assert guess_locale(Evidence(exercise_kind="implement")) == "vi"


def test_check_passes_clean_feedback():
    assert check(preview(entry()), {"CP-001": REFERENCE}) == []


def test_check_flags_leaks_and_invalid_items():
    long_code = "```python\na = 1\nb = 2\nc = 3\n```"
    issues = check(preview(
        entry(how_to_improve=long_code),
        entry(code="explain_strong", why_it_matters="Viết `for i, n in enumerate(nums):` là xong."),
        entry(code="no_hypothesis", next_exercise="CP-999"),
    ), {"CP-001": REFERENCE})
    kinds = sorted(i["issue"] for i in issues)
    assert kinds == ["long_code_block", "next_not_a_candidate", "reference_line_copied"]


def test_a_reference_line_the_student_already_wrote_is_not_a_leak():
    student = "def two_sum(nums, target):\n    for i, n in enumerate(nums):\n        pass"
    item = entry(why_it_matters="Dòng `for i, n in enumerate(nums):` của bạn đúng.")
    assert check(preview(item, final_code=student), {"CP-001": REFERENCE}) == []


async def test_preview_writes_nothing(db_session, tmp_path):
    from app.models import Event, FluencyReport

    at = await _scored_attempt(db_session)
    before_events = (await db_session.execute(select(func.count(Event.id)))).scalar_one()
    report = (await db_session.execute(select(FluencyReport))).scalar_one()
    before_feedback = dict(report.feedback)
    out = await preview_all(db_session, {"S1": at.id}, FakeJudge(), locale="auto")
    assert set(out) == {"S1"} and out["S1"]["exercise"] == "CP-001"
    assert out["S1"]["findings"] and out["S1"]["locale"] == "en"  # the seeded question is English
    json.dumps(out)
    assert (await db_session.execute(select(func.count(Event.id)))).scalar_one() == before_events
    await db_session.refresh(report)
    assert report.feedback == before_feedback
