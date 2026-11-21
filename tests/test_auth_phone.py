"""Signup requires a Vietnamese phone number; learners log in with email or phone."""
import pytest

from app.core.security import hash_password
from app.models import User
from app.schemas.auth import normalize_phone

pytestmark = pytest.mark.asyncio

SIGNUP = {"full_name": "Lan Nguyen", "email": "lan@test.io", "phone": "0912345678",
          "password": "password123", "accept_privacy": True}


@pytest.mark.parametrize("raw", [
    "0912345678", "+84912345678", "84912345678", "0912 345 678", "091.234.5678", "+84 91-234-5678",
    "(091) 234 5678",
])
async def test_normalize_phone_accepts_vietnamese_mobile_formats(raw):
    assert normalize_phone(raw) == "0912345678"


@pytest.mark.parametrize("prefix", ["03", "05", "07", "08", "09"])
async def test_normalize_phone_accepts_every_mobile_network_prefix(prefix):
    assert normalize_phone(f"{prefix}12345678") == f"{prefix}12345678"


@pytest.mark.parametrize("raw", [
    "", "091234567", "09123456789", "0112345678", "0212345678", "0412345678", "0612345678",
    "1912345678", "+1 912345678", "+8491234567", "09123abc78", "84 0912345678",
])
async def test_normalize_phone_rejects_invalid_numbers(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


async def test_signup_stores_normalized_phone(client):
    r = await client.post("/api/auth/signup", json={**SIGNUP, "phone": "+84 912 345 678"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["phone"] == "0912345678"

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["phone"] == "0912345678"


async def test_signup_requires_phone(client):
    body = {k: v for k, v in SIGNUP.items() if k != "phone"}
    assert (await client.post("/api/auth/signup", json=body)).status_code == 422


async def test_signup_rejects_non_vietnamese_phone(client):
    r = await client.post("/api/auth/signup", json={**SIGNUP, "phone": "0212345678"})
    assert r.status_code == 422


async def test_duplicate_phone_conflict(client):
    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    # Same number in another format still collides after normalization.
    r = await client.post("/api/auth/signup", json={**SIGNUP, "email": "other@test.io", "phone": "+84912345678"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Phone number already registered"


async def test_duplicate_email_conflict_keeps_email_detail(client):
    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    r = await client.post("/api/auth/signup", json={**SIGNUP, "phone": "0987654321"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"


@pytest.mark.parametrize("identifier", ["lan@test.io", " LAN@Test.io ", "0912345678", "+84912345678", "0912 345 678"])
async def test_login_with_email_or_phone(client, identifier):
    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    r = await client.post("/api/auth/login", json={"identifier": identifier, "password": "password123"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "lan@test.io"


async def test_login_still_accepts_legacy_email_field(client):
    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    r = await client.post("/api/auth/login", json={"email": "0912345678", "password": "password123"})
    assert r.status_code == 200


async def test_login_wrong_password_with_phone(client):
    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    r = await client.post("/api/auth/login", json={"identifier": "0912345678", "password": "nope-nope"})
    assert r.status_code == 401


async def test_login_unknown_phone(client):
    r = await client.post("/api/auth/login", json={"identifier": "0987654321", "password": "password123"})
    assert r.status_code == 401


async def test_login_rejects_identifier_that_is_neither_email_nor_phone(client):
    r = await client.post("/api/auth/login", json={"identifier": "lan", "password": "password123"})
    assert r.status_code == 422


async def test_existing_user_without_phone_logs_in_by_email_then_adds_phone(client, db_session):
    # Accounts made before this change have no phone.
    db_session.add(User(full_name="Old User", email="old@test.io", password_hash=hash_password("password123")))
    await db_session.commit()

    login = await client.post("/api/auth/login", json={"identifier": "old@test.io", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["phone"] is None
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    patched = await client.patch("/api/auth/me", json={"phone": "+84 33 123 4567"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["phone"] == "0331234567"

    by_phone = await client.post("/api/auth/login", json={"identifier": "0331234567", "password": "password123"})
    assert by_phone.status_code == 200


async def test_update_me_rejects_invalid_or_taken_phone(client, auth_headers):
    assert (await client.patch("/api/auth/me", json={"phone": "12345"}, headers=auth_headers)).status_code == 422

    assert (await client.post("/api/auth/signup", json=SIGNUP)).status_code == 200
    taken = await client.patch("/api/auth/me", json={"phone": "0912345678"}, headers=auth_headers)
    assert taken.status_code == 409
    assert taken.json()["detail"] == "Phone number already registered"


async def test_update_me_keeping_own_phone_is_not_a_conflict(client, auth_headers):
    # auth_headers' user signed up with 0900000001.
    r = await client.patch("/api/auth/me", json={"phone": "0900000001", "full_name": "Renamed"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Renamed"


async def test_staff_cannot_log_in_through_learner_login_by_phone(client, db_session):
    db_session.add(User(full_name="Staff", email="staff@codeprove.production", phone="0977777777",
                        role="admin", password_hash=hash_password("password123")))
    await db_session.commit()
    r = await client.post("/api/auth/login", json={"identifier": "0977777777", "password": "password123"})
    assert r.status_code == 401
