"""Hard caps on the code Ciel shows, whatever it looks like (fix 2026-10-01, CP-001 "heelo" reply)."""
import pytest

import app.features.mentor.guard as guard_mod
from app.core.config import Settings
from app.features.mentor.guard import too_much_code

# The reply from Kiệt's screenshot: no def, renamed variables, 0% overlap with the reference.
LOOP = """Here's a small snippet to get you started:
```python
for i in range(len(nums)):
    complement = target - nums[i]
    if complement in num_dict:
        return [i, num_dict[complement]]
    num_dict[nums[i]] = i
```"""
STARTER = "def two_sum(nums, target):\n    pass"


def fence(code: str) -> str:
    return f"```python\n{code}\n```"


@pytest.fixture(autouse=True)
def caps(monkeypatch):
    monkeypatch.setattr(guard_mod, "get_settings",
                        lambda: Settings(ciel_max_code_lines_per_reply=3, ciel_max_code_lines_per_attempt=8))


def test_the_reported_loop_is_over_the_reply_cap():
    assert too_much_code(LOOP, [], STARTER) is True


def test_three_new_lines_are_fine_and_comments_or_blank_lines_do_not_count():
    assert too_much_code(fence("seen = {}\n\n# check first\nif x in seen:\n    print(x)"), [], STARTER) is False


def test_the_students_own_code_and_the_starter_never_count():
    own = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:"
    quoted = fence(own + "\n        return [seen[target - n], i]")  # quotes 4 own lines, adds 1
    assert too_much_code(quoted, [], own) is False


def test_the_attempt_cap_counts_distinct_lines_and_renaming_does_not_reset_it():
    earlier = [fence("a = 1\nb = 2\nc = 3"), fence("d = 4\ne = 5\nf = 6")]  # 6 distinct lines
    assert too_much_code(fence("x = y + 1\nz = x * 2"), earlier, STARTER) is False  # 8 lines: at the cap
    assert too_much_code(fence("x = y + 1\nz = x * 2\nw = w - 3"), earlier, STARTER) is True  # 9 lines
    # A renamed copy of a line already shown is the same line: it does not add to the count.
    assert too_much_code(fence("q = 1\nr = 2"), [*earlier, fence("x = y + 1\nz = x * 2")], STARTER) is False


async def test_the_heelo_reply_is_withheld_end_to_end(client, db_session, auth_headers, monkeypatch):
    from sqlalchemy import select

    import app.features.mentor.client as client_mod
    import app.features.mentor.service as service_mod
    from app.models import Event, Exercise

    words = "Think about storing each number you have seen together with its index."

    class Scripted:
        _model = "fake"

        def __init__(self):
            self.replies, self.injects = [LOOP, words], []

        async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
            self.injects.append(inject_error)
            return {"text": self.replies.pop(0), "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}

    fake = Scripted()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    db_session.add(Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="c", level="fresher",
                            language="python", summary="s", hint="h", domain_keywords=[], starter_code=STARTER,
                            verification_trap=True, reference_solution="def two_sum(nums, target):\n    return []"))
    await db_session.commit()
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "heelo"}, headers=auth_headers)
    assert r.json()["reply"] == words
    assert fake.injects == [False, False]  # no trap on a greeting
    payload = (await db_session.execute(select(Event).where(Event.type == "AI_REPLY"))).scalar_one().payload
    assert payload["withheldCodeLength"] is True and payload["withheldSolution"] is True
