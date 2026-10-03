"""Authorization boundaries for staff credentials and account management."""
import pytest
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_password
from app.features.admin.service import COOKIE
from app.models import User

pytestmark = pytest.mark.asyncio
ORIGIN = {"Origin": "http://localhost:3000"}


async def add_admin(db_session, email: str, role: str = "admin", first_login: bool = True) -> User:
    user = User(full_name=email.split("@")[0].title(), email=email,
                password_hash=hash_password("Temporary-password-2026"), role=role,
                must_change_password=first_login)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client, email: str) -> object:
    return await client.post("/api/auth/admin/login", headers=ORIGIN,
                             json={"email": email, "password": "Temporary-password-2026"})


async def test_reserved_login_ids_and_public_login_cannot_be_admin(client, db_session):
    signup = await client.post("/api/auth/signup", json={
        "full_name": "Fake Admin", "email": "fake@codeprove.production",
        "password": "password123", "accept_privacy": True,
    })
    assert signup.status_code == 409
    await add_admin(db_session, "trung@codeprove.production", "super_admin")
    public = await client.post("/api/auth/login", json={
        "email": "trung@codeprove.production", "password": "Temporary-password-2026",
    })
    assert public.status_code == 401
    learner = await client.post("/api/auth/signup", json={
        "full_name": "Student", "email": "student@example.com",
        "password": "password123", "accept_privacy": True,
    })
    assert learner.status_code == 200
    staff = await client.post("/api/auth/admin/login", headers=ORIGIN, json={
        "email": "student@example.com", "password": "password123",
    })
    assert staff.status_code == 401


async def test_first_login_can_only_change_password_and_old_session_is_revoked(client, db_session):
    await add_admin(db_session, "kiet@codeprove.production")
    assert (await client.get("/api/admin/audit/me")).status_code == 401
    signed_in = await login(client, "kiet@codeprove.production")
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["must_change_password"] is True
    assert "password_hash" not in signed_in.text
    assert "httponly" in signed_in.headers["set-cookie"].lower()
    old_cookie = client.cookies.get(COOKIE)
    assert old_cookie
    assert (await client.get("/api/admin/admins")).status_code == 403
    assert (await client.get("/api/admin/audit/me")).status_code == 403
    assert (await client.post("/api/auth/admin/change-password", headers=ORIGIN, json={
        "current_password": "bad", "new_password": "A sufficiently long new password",
    })).status_code == 400
    assert (await client.post("/api/auth/admin/change-password", headers=ORIGIN, json={
        "current_password": "Temporary-password-2026", "new_password": "short",
    })).status_code == 422

    changed = await client.post("/api/auth/admin/change-password", headers=ORIGIN, json={
        "current_password": "Temporary-password-2026", "new_password": "A sufficiently long new password",
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    new_cookie = client.cookies.get(COOKIE)
    assert new_cookie != old_cookie
    client.cookies.set(COOKIE, old_cookie)
    assert (await client.get("/api/auth/admin/me")).status_code == 401
    client.cookies.set(COOKIE, new_cookie)
    assert (await client.get("/api/auth/admin/me")).status_code == 200
    assert (await client.post("/api/auth/admin/logout", headers=ORIGIN)).status_code == 204
    assert (await client.get("/api/auth/admin/me")).status_code == 401


async def test_super_admin_manages_regular_admins_and_audit_has_no_secret(client, db_session):
    await add_admin(db_session, "trung@codeprove.production", "super_admin", first_login=False)
    assert (await client.post("/api/auth/admin/login", headers=ORIGIN, json={
        "email": "trung@codeprove.production", "password": "wrong",
    })).status_code == 401
    signed_in = await login(client, "trung@codeprove.production")
    assert signed_in.status_code == 200, signed_in.text
    assert (await client.post("/api/admin/admins", json={
        "full_name": "Kiet", "email": "kiet@codeprove.production",
    })).status_code == 403  # CSRF origin is required even with a valid cookie.

    created = await client.post("/api/admin/admins", headers=ORIGIN, json={
        "full_name": "Kiet", "email": "kiet@codeprove.production",
    })
    assert created.status_code == 201, created.text
    admin_id = created.json()["admin"]["id"]
    password = created.json()["temporary_password"]
    assert password and password not in str(created.json()["admin"])
    assert created.json()["admin"]["role"] == "admin"
    assert created.json()["admin"]["must_change_password"] is True
    assert (await client.post("/api/admin/admins", headers=ORIGIN, json={
        "full_name": "Other", "email": "trung@codeprove.production",
    })).status_code == 409

    roster = await client.get("/api/admin/admins")
    assert roster.status_code == 200
    assert len(roster.json()) == 2
    assert password not in roster.text
    assert "password_hash" not in roster.text
    audit = await client.get("/api/admin/audit")
    assert audit.status_code == 200
    assert {"admin_created", "login_failed"}.issubset({row["action"] for row in audit.json()["items"]})
    personal = await client.get("/api/admin/audit/me")
    assert personal.status_code == 200
    assert {row["id"] for row in personal.json()["items"]}.issubset(
        {row["id"] for row in audit.json()["items"]}
    )
    assert all(row["actor_user_id"] == signed_in.json()["id"] for row in personal.json()["items"])
    assert password not in audit.text

    # Super admins cannot disable or reset themselves through staff management.
    super_id = signed_in.json()["id"]
    assert (await client.patch(f"/api/admin/admins/{super_id}/status", headers=ORIGIN,
                               json={"is_active": False})).status_code == 404
    assert (await client.post(f"/api/admin/admins/{super_id}/reset-password", headers=ORIGIN)).status_code == 404

    disabled = await client.patch(f"/api/admin/admins/{admin_id}/status", headers=ORIGIN,
                                  json={"is_active": False})
    assert disabled.status_code == 200 and disabled.json()["is_active"] is False
    assert (await client.post("/api/auth/admin/login", headers=ORIGIN, json={
        "email": "kiet@codeprove.production", "password": password,
    })).status_code == 401
    assert (await client.patch(f"/api/admin/admins/{admin_id}/status", headers=ORIGIN,
                               json={"is_active": True})).status_code == 200
    reset = await client.post(f"/api/admin/admins/{admin_id}/reset-password", headers=ORIGIN)
    assert reset.status_code == 200
    assert reset.json()["temporary_password"] != password
    assert (await client.get("/api/admin/audit")).status_code == 200
    assert reset.json()["temporary_password"] not in (await client.get("/api/admin/audit")).text


async def test_regular_admin_cannot_manage_other_admins(client, db_session):
    staff = await add_admin(db_session, "phat@codeprove.production", first_login=False)
    assert (await login(client, "phat@codeprove.production")).status_code == 200
    assert (await client.get("/api/admin/admins")).status_code == 403
    assert (await client.get("/api/admin/audit")).status_code == 403
    own = await client.get("/api/admin/audit/me")
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert {row["actor_user_id"] for row in own.json()["items"]} == {staff.id}
    assert (await client.post("/api/admin/admins", headers=ORIGIN, json={
        "full_name": "Minh", "email": "minh@codeprove.production",
    })).status_code == 403


async def test_personal_audit_uses_session_actor_even_with_an_actor_filter(client, db_session):
    first = await add_admin(db_session, "kiet@codeprove.production", first_login=False)
    second = await add_admin(db_session, "phat@codeprove.production", first_login=False)
    assert (await login(client, first.email)).status_code == 200
    first_cookie = client.cookies.get(COOKIE)
    assert (await login(client, second.email)).status_code == 200

    own = await client.get(f"/api/admin/audit/me?actor_id={first.id}")
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert {row["actor_user_id"] for row in own.json()["items"]} == {second.id}
    assert (await client.get("/api/admin/audit")).status_code == 403

    client.cookies.set(COOKIE, first_cookie)
    first_history = await client.get("/api/admin/audit/me")
    assert first_history.status_code == 200
    assert {row["actor_user_id"] for row in first_history.json()["items"]} == {first.id}


async def test_super_admin_must_change_first_and_reset_revokes_staff_session(client, db_session):
    await add_admin(db_session, "trung@codeprove.production", "super_admin")
    await add_admin(db_session, "minh@codeprove.production", first_login=False)
    assert (await login(client, "trung@codeprove.production")).status_code == 200
    assert (await client.get("/api/admin/admins")).status_code == 403
    assert (await client.post("/api/auth/admin/change-password", headers=ORIGIN, json={
        "current_password": "Temporary-password-2026", "new_password": "New private password for Trung",
    })).status_code == 200
    assert (await client.get("/api/admin/admins")).status_code == 200

    assert (await login(client, "minh@codeprove.production")).status_code == 200
    staff_cookie = client.cookies.get(COOKIE)
    assert (await client.get("/api/auth/admin/me")).status_code == 200
    super_login = await client.post("/api/auth/admin/login", headers=ORIGIN, json={
        "email": "trung@codeprove.production", "password": "New private password for Trung",
    })
    assert super_login.status_code == 200
    admin_id = (await db_session.execute(select(User.id).where(User.email == "minh@codeprove.production"))).scalar_one()
    assert (await client.post(f"/api/admin/admins/{admin_id}/reset-password", headers=ORIGIN)).status_code == 200
    client.cookies.set(COOKIE, staff_cookie)
    assert (await client.get("/api/auth/admin/me")).status_code == 401


async def test_google_cannot_link_an_admin_or_create_reserved_id(db_session, monkeypatch):
    from app.features.auth import service as auth_service

    await add_admin(db_session, "trung@codeprove.production", "super_admin", first_login=False)
    monkeypatch.setattr(auth_service, "get_settings", lambda: SimpleNamespace(
        google_client_id="id", google_client_secret="secret", google_redirect_uri="http://test/callback",
    ))

    class FakeResponse:
        status_code = 200

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse({"access_token": "fake"})

        async def get(self, *_args, **_kwargs):
            return FakeResponse({"email": "trung@codeprove.production", "email_verified": True})

    monkeypatch.setattr(auth_service.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    with pytest.raises(ValueError, match="cannot use Google"):
        await auth_service.authenticate_google(db_session, "fake-code")


async def test_bootstrap_creates_four_accounts_without_resetting_existing_passwords(db_session, monkeypatch, capsys):
    from scripts import bootstrap_admins

    monkeypatch.setattr(bootstrap_admins, "async_session_maker", async_sessionmaker(db_session.bind, expire_on_commit=False))
    await bootstrap_admins.bootstrap()
    output = capsys.readouterr().out
    assert output.count("@codeprove.production:") == 4
    accounts = (await db_session.execute(select(User).where(User.role.in_(("admin", "super_admin"))))).scalars().all()
    assert len(accounts) == 4
    assert {u.email for u in accounts if u.role == "super_admin"} == {"trung@codeprove.production"}
    assert all(u.must_change_password for u in accounts)
    hashes = {u.email: u.password_hash for u in accounts}
    await bootstrap_admins.bootstrap()
    assert "already exist" in capsys.readouterr().out
    db_session.expire_all()
    refreshed = (await db_session.execute(select(User).where(User.role.in_(("admin", "super_admin"))))).scalars().all()
    assert {u.email: u.password_hash for u in refreshed} == hashes
