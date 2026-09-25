import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models import User
from app.schemas.auth import SignupIn

pytestmark = pytest.mark.asyncio


async def test_signup_then_me(client):
    r = await client.post("/api/auth/signup", json={"full_name": "Jane Doe", "email": "jane@test.io", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["user"]["email"] == "jane@test.io"

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "Jane Doe"


async def test_signup_accepts_local_email_domain(client):
    r = await client.post(
        "/api/auth/signup",
        json={"full_name": "Local User", "email": "test001@codeprove.local", "password": "password123"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "test001@codeprove.local"


async def test_auth_normalizes_email(client):
    r = await client.post(
        "/api/auth/signup",
        json={"full_name": "Case User", "email": "  CaseUser@CodeProve.Local  ", "password": "password123"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "caseuser@codeprove.local"

    login = await client.post(
        "/api/auth/login",
        json={"email": "CASEUSER@CODEPROVE.LOCAL", "password": "password123"},
    )
    assert login.status_code == 200


async def test_update_me_changes_full_name(client):
    r = await client.post(
        "/api/auth/signup",
        json={"full_name": "Old Name", "email": "patch@test.io", "password": "password123"},
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patched = await client.patch("/api/auth/me", json={"full_name": "New Name"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "New Name"

    # Persisted: a fresh GET returns the updated name.
    me = await client.get("/api/auth/me", headers=headers)
    assert me.json()["full_name"] == "New Name"


async def test_update_me_requires_auth(client):
    r = await client.patch("/api/auth/me", json={"full_name": "X"})
    assert r.status_code == 401


async def test_update_me_rejects_short_name(client):
    r = await client.post(
        "/api/auth/signup",
        json={"full_name": "Valid Name", "email": "short@test.io", "password": "password123"},
    )
    token = r.json()["access_token"]
    bad = await client.patch(
        "/api/auth/me", json={"full_name": "A"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert bad.status_code == 422


async def test_login_wrong_password(client):
    await client.post("/api/auth/signup", json={"full_name": "Bob", "email": "bob@test.io", "password": "password123"})
    r = await client.post("/api/auth/login", json={"email": "bob@test.io", "password": "nope"})
    assert r.status_code == 401


async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_duplicate_email_conflict(client):
    first = await client.post(
        "/api/auth/signup",
        json={"full_name": "Amy", "email": "amy@test.io", "password": "password123"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/signup",
        json={"full_name": "Amy Two", "email": "amy@test.io", "password": "password456"},
    )
    assert second.status_code == 409


def _commit_rival_after_existence_check(db_session, monkeypatch, email: str) -> None:
    """Simulate a concurrent signup: let create_user's existence SELECT run (and
    find nothing), then commit a rival row with the same email before its insert."""
    original_execute = db_session.execute

    async def racing_execute(*args, **kwargs):
        result = await original_execute(*args, **kwargs)
        monkeypatch.setattr(db_session, "execute", original_execute)
        db_session.add(User(full_name="Rival", email=email, password_hash=hash_password("rival-pass-123")))
        await db_session.commit()
        return result

    monkeypatch.setattr(db_session, "execute", racing_execute)


async def test_create_user_race_raises_email_taken(db_session, monkeypatch):
    from app.features.auth import service

    _commit_rival_after_existence_check(db_session, monkeypatch, "race@test.io")
    data = SignupIn(full_name="Racer", email="race@test.io", password="password123")
    with pytest.raises(ValueError, match="email_taken"):
        await service.create_user(db_session, data)

    # The session was rolled back and stays usable; only the rival row exists.
    rows = (await db_session.execute(select(User).where(User.email == "race@test.io"))).scalars().all()
    assert [u.full_name for u in rows] == ["Rival"]


async def test_concurrent_duplicate_signup_returns_409(client, db_session, monkeypatch):
    _commit_rival_after_existence_check(db_session, monkeypatch, "race2@test.io")
    r = await client.post(
        "/api/auth/signup",
        json={"full_name": "Racer", "email": "race2@test.io", "password": "password123"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"

    # The winning signup is intact and can still log in.
    login = await client.post("/api/auth/login", json={"email": "race2@test.io", "password": "rival-pass-123"})
    assert login.status_code == 200


async def test_non_integer_token_subject_returns_401(client):
    # A validly-signed token whose subject is not an integer must yield 401, not 500.
    token = create_access_token("not-an-int")
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_oauth_state_carries_redirect_roundtrip():
    # The OAuth state (a signed JWT) must carry the redirect origin so it
    # survives the round-trip to Google and back to the callback.
    from app.features.auth import service

    state = service.create_oauth_state("http://localhost:3000")
    payload = service.decode_oauth_state(state)
    assert payload is not None
    assert payload.get("redirect") == "http://localhost:3000"
    assert service.decode_oauth_state("garbage") is None


async def test_frontend_origin_allowlist_blocks_open_redirect():
    # Only allowlisted origins (cors_origins + frontend_url) pass; anything else
    # (a foreign host, junk, None) is rejected so the callback can't be hijacked.
    from app.features.auth import router

    assert router._validate_frontend_origin("http://localhost:3000/auth/callback") == "http://localhost:3000"
    assert router._validate_frontend_origin("https://evil.example.com/auth/callback") is None
    assert router._validate_frontend_origin("not-a-url") is None
    assert router._validate_frontend_origin(None) is None
