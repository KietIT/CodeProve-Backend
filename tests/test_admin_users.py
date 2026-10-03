"""Admin learner directory uses real attempts and keeps staff/private data out."""
import pytest

from app.core.security import hash_password
from app.models import Attempt, Exercise, User

pytestmark = pytest.mark.asyncio


async def test_directory_requires_ready_admin_and_excludes_staff(client, db_session):
    learner = User(full_name="Learner", email="learner@example.com", password_hash="private-hash")
    staff = User(full_name="Staff", email="staff@codeprove.production", password_hash=hash_password("temporary-password-2026"),
                 role="admin", must_change_password=True)
    db_session.add_all([learner, staff])
    await db_session.commit()
    await db_session.refresh(learner)
    await db_session.refresh(staff)

    assert (await client.get("/api/admin/users")).status_code == 401
    login = await client.post("/api/auth/admin/login", headers={"Origin": "http://localhost:3000"},
                              json={"email": staff.email, "password": "temporary-password-2026"})
    assert login.status_code == 200
    assert (await client.get("/api/admin/users")).status_code == 403
    assert (await client.get(f"/api/admin/users/{learner.id}")).status_code == 403

    changed = await client.post("/api/auth/admin/change-password", headers={"Origin": "http://localhost:3000"},
                                json={"current_password": "temporary-password-2026", "new_password": "another-long-password-2026"})
    assert changed.status_code == 200
    listing = await client.get("/api/admin/users")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == learner.id
    assert "password_hash" not in listing.text
    assert "plan" not in listing.text
    assert (await client.get(f"/api/admin/users/{staff.id}")).status_code == 404


async def test_directory_filters_paginates_and_counts_attempts(client, db_session):
    staff = User(full_name="Staff", email="staff@codeprove.production", password_hash=hash_password("temporary-password-2026"),
                 role="admin", must_change_password=False)
    first = User(full_name="Alpha One", email="alpha@example.com", password_hash="private-one")
    second = User(full_name="Beta Two", email="beta@example.com", password_hash="private-two", is_active=False)
    exercise = Exercise(code="CP-999", title="Test", difficulty="Easy", category="test", level="fresher")
    db_session.add_all([staff, first, second, exercise])
    await db_session.commit()
    for item in (first, second, exercise):
        await db_session.refresh(item)
    db_session.add_all([
        Attempt(user_id=first.id, exercise_id=exercise.id, status="in_progress"),
        Attempt(user_id=first.id, exercise_id=exercise.id, status="submitted"),
        Attempt(user_id=first.id, exercise_id=exercise.id, status="scored", score=80),
        Attempt(user_id=first.id, exercise_id=exercise.id, status="scored", score=90),
    ])
    await db_session.commit()
    assert (await client.post("/api/auth/admin/login", headers={"Origin": "http://localhost:3000"},
                              json={"email": staff.email, "password": "temporary-password-2026"})).status_code == 200

    page = await client.get("/api/admin/users?limit=1&offset=0")
    assert page.status_code == 200 and page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert (await client.get("/api/admin/users?limit=1&offset=1")).json()["total"] == 2
    assert (await client.get("/api/admin/users?account_status=inactive")).json()["items"][0]["id"] == second.id
    assert (await client.get("/api/admin/users?search=Alpha")).json()["items"][0]["id"] == first.id
    assert (await client.get(f"/api/admin/users?search={first.id}")).json()["items"][0]["id"] == first.id
    assert (await client.get("/api/admin/users?search=%25")).json()["total"] == 0
    assert (await client.get("/api/admin/users?limit=101")).status_code == 422

    detail = await client.get(f"/api/admin/users/{first.id}")
    assert detail.status_code == 200
    assert detail.json()["attempts"] == 4
    assert detail.json()["completed"] == 3
    assert detail.json()["average_score"] == 85
    assert detail.json()["last_attempt_at"] is not None
    assert (await client.get(f"/api/admin/users/{second.id}")).json()["average_score"] is None
    assert (await client.get("/api/admin/users/999999")).status_code == 404
