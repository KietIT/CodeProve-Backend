import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


async def test_signup_then_me(client):
    r = await client.post("/api/auth/signup", json={"full_name": "Jane Doe", "email": "jane@test.io", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["user"]["email"] == "jane@test.io"

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "Jane Doe"


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


async def test_non_integer_token_subject_returns_401(client):
    # A validly-signed token whose subject is not an integer must yield 401, not 500.
    token = create_access_token("not-an-int")
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
