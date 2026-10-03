"""Overview counts only real learner records and requires a ready admin session."""
from datetime import datetime, timezone

import pytest

from app.core.security import hash_password
from app.models import Attempt, Exercise, User

pytestmark = pytest.mark.asyncio


async def test_overview_authorization_and_real_counts(client, db_session):
    staff = User(full_name="Admin", email="admin@codeprove.production",
                 password_hash=hash_password("temporary-password-2026"),
                 role="admin", must_change_password=True)
    learners = [
        User(full_name=f"Learner {number}", email=f"learner{number}@example.com",
             password_hash="private-hash", is_active=number % 2 == 0,
             created_at=datetime(2026, 9, number, tzinfo=timezone.utc))
        for number in range(1, 6)
    ]
    exercise = Exercise(code="CP-998", title="Test", difficulty="Easy", category="test", level="fresher")
    db_session.add_all([staff, *learners, exercise])
    await db_session.commit()
    for item in (staff, *learners, exercise):
        await db_session.refresh(item)
    db_session.add_all([
        Attempt(user_id=learners[0].id, exercise_id=exercise.id, status="submitted"),
        Attempt(user_id=learners[0].id, exercise_id=exercise.id, status="scored", score=80),
        Attempt(user_id=staff.id, exercise_id=exercise.id, status="scored", score=100),
    ])
    await db_session.commit()

    assert (await client.get("/api/admin/overview")).status_code == 401
    signed_in = await client.post("/api/auth/admin/login", headers={"Origin": "http://localhost:3000"},
                                  json={"email": staff.email, "password": "temporary-password-2026"})
    assert signed_in.status_code == 200
    assert (await client.get("/api/admin/overview")).status_code == 403
    changed = await client.post("/api/auth/admin/change-password", headers={"Origin": "http://localhost:3000"},
                                json={"current_password": "temporary-password-2026", "new_password": "another-long-password-2026"})
    assert changed.status_code == 200

    response = await client.get("/api/admin/overview")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["users_total"] == 5
    assert body["users_active"] == 2
    assert body["attempts_total"] == 2
    assert [user["id"] for user in body["recent_users"]] == [user.id for user in reversed(learners[1:])]
    assert all(user["id"] != staff.id for user in body["recent_users"])
    assert "password_hash" not in response.text
    assert "plan" not in response.text


async def test_overview_empty_database_returns_zero_counts(client, db_session):
    staff = User(full_name="Admin", email="admin@codeprove.production",
                 password_hash=hash_password("temporary-password-2026"), role="admin")
    db_session.add(staff)
    await db_session.commit()
    signed_in = await client.post("/api/auth/admin/login", headers={"Origin": "http://localhost:3000"},
                                  json={"email": staff.email, "password": "temporary-password-2026"})
    assert signed_in.status_code == 200
    response = await client.get("/api/admin/overview")
    assert response.status_code == 200
    assert response.json() == {"users_total": 0, "users_active": 0, "attempts_total": 0, "recent_users": []}
