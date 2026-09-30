"""P2.2: the locate step of debug exercises (hints, location, reason)."""
from sqlalchemy import select

STARTER = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):   # bug: skips n\n        total += i\n    return total"
META = {"regions": [[3]], "explanation_vi": "Dòng 3 bỏ sót n.", "explanation_en": "Line 3 skips n.",
        "hint_vi": "Lỗi ở biên vòng lặp.", "hint_en": "A loop-boundary bug."}


async def _attempt(client, db_session, auth_headers, kind="debug", meta=META) -> int:
    from app.models import Exercise

    db_session.add(Exercise(code="CP-004", title="Off by one", difficulty="Easy", category="Debugging",
                            level="fresher", language="python", summary="s", kind=kind, starter_code=STARTER,
                            hint="h", domain_keywords=[], debug_meta=meta))
    await db_session.commit()
    r = await client.post("/api/attempts", json={"exercise_code": "CP-004"}, headers=auth_headers)
    return r.json()["attempt_id"]


async def _events(db_session, aid, type_):
    from app.models import Event

    rows = (await db_session.execute(select(Event).where(Event.attempt_id == aid, Event.type == type_)
                                     .order_by(Event.id))).scalars().all()
    return [r.payload for r in rows]


async def _state(client, aid, auth_headers, locale="en"):
    return (await client.get(f"/api/attempts/{aid}?locale={locale}", headers=auth_headers)).json()["debug"]


async def test_hints_come_in_two_steps_and_never_name_the_line(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    h1 = await client.post(f"/api/attempts/{aid}/debug/hint?locale=vi", headers=auth_headers)
    assert h1.json() == {"step": 1, "text": "Lỗi ở biên vòng lặp."}
    h2 = await client.post(f"/api/attempts/{aid}/debug/hint?locale=en", headers=auth_headers)
    assert h2.json() == {"step": 2, "text": "Look closely at lines 2–4."}
    third = await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)
    assert third.status_code == 409
    assert await _events(db_session, aid, "DEBUG_HINT") == [{"step": 1}, {"step": 2}]
    # A reload restores the hints already bought, in the requested language.
    assert await _state(client, aid, auth_headers, "vi") == {
        "located": False, "hints_used": 2, "hints": ["Lỗi ở biên vòng lặp.", "Xem kỹ các dòng 2–4."]}


async def test_locating_records_lines_reason_and_hints_without_grading(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)
    r = await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers,
                          json={"lines": [3, 3], "reason": "  range stops before n  "})
    assert r.status_code == 200 and r.json() == {"ok": True}  # no right/wrong before submit
    assert await _events(db_session, aid, "LOCATE") == [
        {"lines": [3], "reason": "range stops before n", "skipped": False, "hintsUsed": 1}]
    assert (await _state(client, aid, auth_headers))["located"] is True
    # Once located, no second location and no more hints.
    again = await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers,
                              json={"lines": [4], "reason": "x"})
    assert again.status_code == 409
    assert (await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)).status_code == 409


async def test_skipping_records_an_empty_location(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers,
                          json={"lines": [2], "reason": "ignored", "skipped": True})
    assert r.status_code == 200
    assert await _events(db_session, aid, "LOCATE") == [
        {"lines": [], "reason": "", "skipped": True, "hintsUsed": 0}]


async def test_invalid_locations_are_rejected(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    for body in ({"lines": [], "reason": "x"},              # nothing selected
                 {"lines": [1, 2, 3], "reason": "x"},       # more than regions + 1 lines
                 {"lines": [6], "reason": "x"},             # the served starter has 5 lines
                 {"lines": [3], "reason": "x" * 501}):      # reason too long
        r = await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers, json=body)
        assert r.status_code == 422, body
    assert await _events(db_session, aid, "LOCATE") == []


async def test_no_locate_step_outside_debug_exercises_or_after_submit(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers, kind="implement", meta=None)
    assert (await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)).status_code == 400
    assert await _state(client, aid, auth_headers) is None


async def test_nothing_after_submit(client, db_session, auth_headers):
    from app.models import Attempt

    aid = await _attempt(client, db_session, auth_headers)
    attempt = (await db_session.execute(select(Attempt).where(Attempt.id == aid))).scalar_one()
    attempt.status = "submitted"
    await db_session.commit()
    assert (await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)).status_code == 409
    r = await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers, json={"lines": [3], "reason": "x"})
    assert r.status_code == 409


async def test_responses_never_contain_the_answer(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)
    await client.post(f"/api/attempts/{aid}/debug/hint", headers=auth_headers)
    state = await client.get(f"/api/attempts/{aid}", headers=auth_headers)
    body = state.text
    assert "regions" not in body and "skips n" not in body and "explanation" not in body
