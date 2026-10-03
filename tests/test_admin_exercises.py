"""Exercise authoring must preserve learner isolation and independent review."""
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.features.admin import exercises as workflow
from app.features.content.schema import CONTENT_DIR
from app.features.content.sync import sync_content
from app.models import AdminAuditLog, Exercise, ExerciseDraft, TestCase, User

pytestmark = pytest.mark.asyncio
ORIGIN = {"Origin": "http://localhost:3000"}


async def staff(db, name: str, role: str = "admin") -> User:
    user = User(full_name=name, email=f"{name.lower()}@codeprove.production",
                password_hash=hash_password("Temporary-password-2026"), role=role,
                must_change_password=False)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def sign_in(client, name: str) -> None:
    response = await client.post("/api/auth/admin/login", headers=ORIGIN, json={
        "email": f"{name.lower()}@codeprove.production", "password": "Temporary-password-2026",
    })
    assert response.status_code == 200, response.text


def payload() -> dict:
    return {
        "code": "CP-901", "title": "Identity", "difficulty": "Easy", "category": "Algorithms",
        "level": "fresher", "kind": "implement", "language": "python", "summary": "Return the input",
        "starter_code": "def f(x):\n    pass", "hint": "Use return", "reference_solution": "def f(x):\n    return x",
        "tests": [{"description": "visible", "input": "f(1)", "expected": "1", "category": "happy", "hidden": False},
                  {"description": "private", "input": "f(2)", "expected": "2", "category": "boundary", "hidden": True}],
        "mutants": [], "skills": [],
    }


async def test_draft_review_publish_is_private_versioned_and_audited(client, db_session, auth_headers, monkeypatch):
    author = await staff(db_session, "Kiet")
    reviewer = await staff(db_session, "Phat")
    await staff(db_session, "Trung", "super_admin")

    async def validated(*_args):
        return []  # The sandbox validator has its own tests; this checks the workflow around it.

    monkeypatch.setattr(workflow, "validate_content", validated)
    assert (await client.get("/api/admin/exercises")).status_code == 401
    await sign_in(client, "Kiet")
    assert (await client.post("/api/admin/exercises/drafts", json=payload())).status_code == 403
    created = await client.post("/api/admin/exercises/drafts", headers=ORIGIN, json=payload())
    assert created.status_code == 201, created.text
    assert created.json()["revision"] == 1
    assert created.json()["author_user_id"] == author.id
    listing = await client.get("/api/admin/exercises?status=draft&q=CP-901")
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["code"] == "CP-901"
    assert "reference_solution" not in listing.text
    assert "private" not in listing.text
    assert (await client.get("/api/exercises/CP-901", headers=auth_headers)).status_code == 404

    edited = payload()
    edited["summary"] = "Return x unchanged"
    saved = await client.put("/api/admin/exercises/drafts/CP-901", headers=ORIGIN,
                             json={"expected_revision": 1, "payload": edited})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 2
    stale = await client.put("/api/admin/exercises/drafts/CP-901", headers=ORIGIN,
                             json={"expected_revision": 1, "payload": edited})
    assert stale.status_code == 409
    assert (await client.post("/api/admin/exercises/drafts/CP-901/validate", headers=ORIGIN,
                              json={"expected_revision": 2})).json()["valid"] is True
    submitted = await client.post("/api/admin/exercises/drafts/CP-901/submit", headers=ORIGIN,
                                  json={"expected_revision": 2})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "review"
    assert (await client.post("/api/admin/exercises/drafts/CP-901/approve", headers=ORIGIN,
                              json={"expected_revision": 3})).status_code == 403
    assert (await client.post("/api/admin/exercises/drafts/CP-901/publish", headers=ORIGIN,
                              json={"expected_revision": 3})).status_code == 409
    assert (await client.get("/api/exercises/CP-901", headers=auth_headers)).status_code == 404

    await sign_in(client, "Phat")
    approved = await client.post("/api/admin/exercises/drafts/CP-901/approve", headers=ORIGIN,
                                 json={"expected_revision": 3})
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewer_user_id"] == reviewer.id
    assert (await client.put("/api/admin/exercises/drafts/CP-901", headers=ORIGIN,
                             json={"expected_revision": 4, "payload": edited})).status_code == 409

    async def no_longer_valid(*_args):
        return ["reference solution fails after review"]

    monkeypatch.setattr(workflow, "validate_content", no_longer_valid)
    blocked = await client.post("/api/admin/exercises/drafts/CP-901/publish", headers=ORIGIN,
                                json={"expected_revision": 4})
    assert blocked.status_code == 422
    assert (await client.get("/api/exercises/CP-901", headers=auth_headers)).status_code == 404
    monkeypatch.setattr(workflow, "validate_content", validated)
    published = await client.post("/api/admin/exercises/drafts/CP-901/publish", headers=ORIGIN,
                                  json={"expected_revision": 4})
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    ex = (await db_session.execute(select(Exercise).where(Exercise.code == "CP-901"))).scalar_one()
    assert ex.content_source == "admin"
    assert ex.summary == "Return x unchanged"
    cases = (await db_session.execute(select(TestCase).where(TestCase.exercise_id == ex.id))).scalars().all()
    assert len(cases) == 2
    public = await client.get("/api/exercises/CP-901", headers=auth_headers)
    assert public.status_code == 200, public.text
    assert "reference_solution" not in public.text
    assert "private" not in public.text
    assert "f(2)" not in public.text

    await sign_in(client, "Trung")
    audit = await client.get("/api/admin/audit?exercise_code=CP-901")
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()["items"]}
    assert {"exercise_draft_created", "exercise_draft_updated", "exercise_submitted",
            "exercise_approved", "exercise_published"}.issubset(actions)
    assert "f(2)" not in audit.text
    assert "def f(x)" not in audit.text
    changed = next(item for item in audit.json()["items"] if item["action"] == "exercise_draft_updated")
    assert changed["detail"] == "revision 2; fields: summary"


async def test_admin_managed_exercise_cannot_be_overwritten_by_file_sync(db_session):
    ex = Exercise(code="CP-004", title="Managed", difficulty="Easy", category="Algorithms",
                  level="fresher", kind="implement", language="python", summary="keep",
                  starter_code="def f(): pass", hint="", domain_keywords=[], content_source="admin")
    db_session.add(ex)
    await db_session.commit()
    result = await sync_content(db_session, [CONTENT_DIR / "CP-004.json"], apply=True)
    assert result == [{"code": "CP-004", "status": "skipped", "reason": "managed by admin review workflow"}]
    assert ex.summary == "keep"


async def test_edit_existing_exercise_does_not_change_public_version_until_publish(
        client, db_session, auth_headers, monkeypatch):
    await staff(db_session, "Kiet")
    await staff(db_session, "Phat")
    ex = Exercise(code="CP-902", title="Before", difficulty="Easy", category="Algorithms",
                  level="fresher", kind="implement", language="python", summary="Old statement",
                  starter_code="def f(x):\n    pass", hint="Old hint", domain_keywords=[],
                  reference_solution="def f(x):\n    return x", content_source="file")
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="f(1)", expected_output="1",
                            description="visible", category="happy", is_hidden=False, order_index=1))
    await db_session.commit()

    async def validated(*_args):
        return []

    monkeypatch.setattr(workflow, "validate_content", validated)
    await sign_in(client, "Kiet")
    listing = await client.get("/api/admin/exercises?status=published&q=CP-902")
    assert listing.status_code == 200 and listing.json()["total"] == 1
    started = await client.post("/api/admin/exercises/CP-902/draft", headers=ORIGIN)
    assert started.status_code == 201, started.text
    assert started.json()["payload"]["tests"][0]["description"] == "visible"
    changed = started.json()["payload"]
    changed["summary"] = "New statement"
    saved = await client.put("/api/admin/exercises/drafts/CP-902", headers=ORIGIN,
                             json={"expected_revision": 1, "payload": changed})
    assert saved.status_code == 200, saved.text
    before = await client.get("/api/exercises/CP-902", headers=auth_headers)
    assert before.status_code == 200 and before.json()["summary"] == "Old statement"
    assert (await client.post("/api/admin/exercises/drafts/CP-902/submit", headers=ORIGIN,
                              json={"expected_revision": 2})).status_code == 200
    await sign_in(client, "Phat")
    assert (await client.post("/api/admin/exercises/drafts/CP-902/approve", headers=ORIGIN,
                              json={"expected_revision": 3})).status_code == 200
    assert (await client.post("/api/admin/exercises/drafts/CP-902/publish", headers=ORIGIN,
                              json={"expected_revision": 4})).status_code == 200
    after = await client.get("/api/exercises/CP-902", headers=auth_headers)
    assert after.status_code == 200 and after.json()["summary"] == "New statement"
    assert ex.content_source == "admin"


async def test_invalid_content_cannot_be_submitted(client, db_session, monkeypatch):
    await staff(db_session, "Minh")
    await sign_in(client, "Minh")

    async def invalid(*_args):
        return ["hidden tests: 1 (need 5-8)"]

    monkeypatch.setattr(workflow, "validate_content", invalid)
    assert (await client.post("/api/admin/exercises/drafts", headers=ORIGIN, json=payload())).status_code == 201
    response = await client.post("/api/admin/exercises/drafts/CP-901/submit", headers=ORIGIN,
                                 json={"expected_revision": 1})
    assert response.status_code == 422
    row = (await db_session.execute(select(ExerciseDraft))).scalar_one()
    assert row.status == "draft"
    assert (await db_session.execute(select(AdminAuditLog).where(
        AdminAuditLog.action == "exercise_submitted"))).scalar_one_or_none() is None
