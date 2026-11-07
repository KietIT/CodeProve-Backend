"""Payment-only staff can read financial reports, never other admin resources."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import create_access_token, verify_password
from app.models import User
from scripts import bootstrap_payment_viewer

pytestmark = pytest.mark.asyncio
ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "viewer-test-password"


async def provision(db_session, monkeypatch):
    monkeypatch.setattr(bootstrap_payment_viewer, "async_session_maker",
                        async_sessionmaker(db_session.bind, expire_on_commit=False))
    assert await bootstrap_payment_viewer.bootstrap(PASSWORD) is True
    return (await db_session.execute(select(User).where(User.email == bootstrap_payment_viewer.EMAIL))).scalar_one()


async def sign_in(client):
    response = await client.post("/api/auth/admin/login", headers=ORIGIN,
                                 json={"email": bootstrap_payment_viewer.EMAIL, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "payment_viewer"
    assert response.json()["must_change_password"] is False
    assert "httponly" in response.headers["set-cookie"].lower()


async def test_viewer_can_read_payments_and_logout(client, db_session, monkeypatch):
    await provision(db_session, monkeypatch)
    await sign_in(client)
    assert (await client.get("/api/auth/admin/me")).json()["role"] == "payment_viewer"
    history = await client.get("/api/admin/payments", params={"search": "student", "limit": 10})
    assert history.status_code == 200, history.text
    assert history.json()["items"] == []
    summary = await client.get("/api/admin/payments/summary", params={"days": 7})
    assert summary.status_code == 200, summary.text
    assert len(summary.json()["by_day"]) == 7
    assert (await client.post("/api/auth/admin/logout", headers=ORIGIN)).status_code == 204
    assert (await client.get("/api/admin/payments")).status_code == 401


async def test_viewer_is_denied_every_other_admin_route(client, db_session, monkeypatch):
    await provision(db_session, monkeypatch)
    await sign_in(client)
    # Exercise every registered non-payment admin route, including mutations,
    # with bodies valid enough to distinguish authorization from validation.
    from app.main import create_app
    for route in create_app().routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/admin/") or path.startswith("/api/admin/payments"):
            continue
        path = path.replace("{admin_id}", "1").replace("{user_id}", "1").replace("{code}", "CP-001")
        for method in route.methods - {"HEAD", "OPTIONS"}:
            response = await client.request(method, path, headers=ORIGIN, json={})
            assert response.status_code == 403, (method, path, response.status_code, response.text)


async def test_viewer_cannot_use_learner_auth_and_disable_is_immediate(client, db_session, monkeypatch):
    user = await provision(db_session, monkeypatch)
    assert (await client.post("/api/auth/login", json={
        "email": user.email, "password": PASSWORD,
    })).status_code == 401
    assert (await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {create_access_token(str(user.id))}",
    })).status_code == 401
    await sign_in(client)
    user.is_active = False
    await db_session.commit()
    assert (await client.get("/api/admin/payments")).status_code == 401


async def test_bootstrap_is_idempotent_and_does_not_promote_learner(client, db_session, monkeypatch):
    # The public signup cannot claim the designated staff ID before provisioning.
    response = await client.post("/api/auth/signup", json={
        "full_name": "Someone", "email": bootstrap_payment_viewer.EMAIL,
        "password": PASSWORD, "accept_privacy": True,
    })
    assert response.status_code == 409
    user = await provision(db_session, monkeypatch)
    assert verify_password(PASSWORD, user.password_hash)
    assert await bootstrap_payment_viewer.bootstrap("different-password") is False
    await db_session.refresh(user)
    assert verify_password(PASSWORD, user.password_hash)
    user.role = "user"
    await db_session.commit()
    with pytest.raises(RuntimeError, match="Conflicting account"):
        await bootstrap_payment_viewer.bootstrap(PASSWORD)


async def test_viewer_must_change_password_when_reset_is_required(client, db_session, monkeypatch):
    user = await provision(db_session, monkeypatch)
    user.must_change_password = True
    await db_session.commit()
    response = await client.post("/api/auth/admin/login", headers=ORIGIN,
                                 json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    assert (await client.get("/api/admin/payments")).status_code == 403
    changed = await client.post("/api/auth/admin/change-password", headers=ORIGIN, json={
        "current_password": PASSWORD, "new_password": "new-viewer-test-password",
    })
    assert changed.status_code == 200, changed.text
    assert (await client.get("/api/admin/payments")).status_code == 200
