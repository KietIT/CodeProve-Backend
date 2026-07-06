import pytest
from datetime import date

pytestmark = pytest.mark.asyncio

_FULL_PAYLOAD = {
    "buggy_code": "def is_prime(n):\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True",
    "buggy_line": 2,
    "bug_category": "off-by-one",
    "hint_1_vi": "Xem lại vòng lặp",
    "hint_1_en": "Look at the loop",
    "hint_2_vi": "Số 0 và 1 có được xử lý đúng không?",
    "hint_2_en": "Are 0 and 1 handled correctly?",
    "explanation_vi": "Thiếu kiểm tra n < 2, nên 0 và 1 bị coi là số nguyên tố.",
    "explanation_en": "The n < 2 check is missing, so 0 and 1 count as prime.",
}


class FakeJudgeClient:
    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        assert "Problem title:" in user
        return dict(_FULL_PAYLOAD)


class EmptyJudgeClient:
    """Simulates a truncated/unparseable LLM response - judge() falls back to {}."""

    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        return {}


class MissingExplanationJudgeClient:
    """Valid code/line but one explanation language missing - must be rejected."""

    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        payload = dict(_FULL_PAYLOAD)
        del payload["explanation_vi"]
        return payload


class RecordingJudgeClient:
    """Records the kwargs it was called with so tests can assert on max_tokens."""

    _model = "fake"

    def __init__(self):
        self.calls = []

    async def judge(self, system, user, max_tokens=300):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return dict(_FULL_PAYLOAD)


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    fake = FakeJudgeClient()
    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: fake)


async def test_generate_challenge_creates_row(db_session):
    from app.features.daily.content import generate_challenge
    from app.models import DailyChallenge

    challenge = await generate_challenge(db_session, date(2026, 7, 4))
    assert isinstance(challenge, DailyChallenge)
    assert challenge.challenge_date == date(2026, 7, 4)
    assert challenge.buggy_line == 2
    assert challenge.bug_category == "off-by-one"
    assert challenge.prompt_title_vi  # picked from the bank, non-empty
    assert challenge.prompt_title_en
    assert challenge.explanation_vi.startswith("Thiếu")
    assert challenge.explanation_en.startswith("The n < 2")


async def test_generate_challenge_avoids_titles_used_in_last_30_days(db_session):
    from app.features.daily.content import generate_challenge
    from app.features.daily.prompts_bank import DAILY_PROMPTS
    from app.models import DailyChallenge
    from datetime import timedelta

    # Fill every prompt except the last one with recent challenges, so the
    # generator is forced to pick the one remaining unused title. Exclusion
    # matches on the English title.
    today = date(2026, 7, 4)
    for i, prompt in enumerate(DAILY_PROMPTS[:-1]):
        db_session.add(
            DailyChallenge(
                challenge_date=today - timedelta(days=i + 1),
                prompt_title_vi=prompt["vi"], prompt_title_en=prompt["en"],
                buggy_code="x", buggy_line=1, bug_category="c",
                hint_1_vi="h", hint_1_en="h", hint_2_vi="h", hint_2_en="h",
                explanation_vi="e", explanation_en="e",
            )
        )
    await db_session.commit()

    challenge = await generate_challenge(db_session, today)
    assert challenge.prompt_title_en == DAILY_PROMPTS[-1]["en"]
    assert challenge.prompt_title_vi == DAILY_PROMPTS[-1]["vi"]


async def test_generate_challenge_raises_on_empty_judge_response(db_session, monkeypatch):
    from app.features.daily.content import DailyGenerationError, generate_challenge
    from app.models import DailyChallenge
    from sqlalchemy import select
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: EmptyJudgeClient())

    with pytest.raises(DailyGenerationError):
        await generate_challenge(db_session, date(2026, 7, 4))

    rows = (await db_session.execute(select(DailyChallenge))).scalars().all()
    assert rows == []


async def test_generate_challenge_raises_when_one_explanation_language_missing(db_session, monkeypatch):
    from app.features.daily.content import DailyGenerationError, generate_challenge
    from app.models import DailyChallenge
    from sqlalchemy import select
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: MissingExplanationJudgeClient())

    with pytest.raises(DailyGenerationError):
        await generate_challenge(db_session, date(2026, 7, 4))

    rows = (await db_session.execute(select(DailyChallenge))).scalars().all()
    assert rows == []


async def test_generate_challenge_requests_max_tokens_1500(db_session, monkeypatch):
    from app.features.daily.content import generate_challenge
    import app.features.daily.content as content_mod

    recorder = RecordingJudgeClient()
    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: recorder)

    await generate_challenge(db_session, date(2026, 7, 4))

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["max_tokens"] == 1500
