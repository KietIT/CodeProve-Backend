import pytest

pytestmark = pytest.mark.asyncio


async def _seed_exercise(db_session):
    from app.models import Exercise
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", acceptance=57.7, summary="s",
                  starter_code="def f():\n    return []", hint="h", domain_keywords=["algorithms"])
    db_session.add(ex); await db_session.commit()


async def test_create_attempt_and_events(client, db_session, auth_headers):
    await _seed_exercise(db_session)
    r = await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)
    assert r.status_code == 200
    aid = r.json()["attempt_id"]

    ev = await client.post(f"/api/attempts/{aid}/events", headers=auth_headers, json={"events": [
        {"type": "CODE_EDIT", "ts": 1000, "payload": {"charsAdded": 10}},
        {"type": "PASTE", "ts": 1100, "payload": {"length": 200}, "integrity_flags": ["BURST_PASTE"]},
    ]})
    assert ev.json()["ingested"] == 2

    snap = await client.post(f"/api/attempts/{aid}/snapshots", headers=auth_headers,
                             json={"version": 1, "source_code": "print(1)"})
    assert snap.json()["ok"] is True

    state = await client.get(f"/api/attempts/{aid}", headers=auth_headers)
    assert state.json()["latest_code"] == "print(1)"
    assert state.json()["status"] == "in_progress"
