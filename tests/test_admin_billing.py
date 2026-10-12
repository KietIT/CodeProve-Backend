"""Admins see plans and money, and can give or end a learner's plan with an audit entry."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import AdminAuditLog, Order, Subscription, User

pytestmark = pytest.mark.asyncio

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "temporary-password-2026"


async def _people(db_session, client, *, sign_in=True) -> tuple[User, User]:
    staff = User(full_name="Staff", email="staff@codeprove.production", password_hash=hash_password(PASSWORD),
                 role="admin", must_change_password=False)
    learner = User(full_name="Learner", email="learner@example.com", password_hash=hash_password("password123"))
    db_session.add_all([staff, learner])
    await db_session.commit()
    for person in (staff, learner):
        await db_session.refresh(person)
    if sign_in:
        login = await client.post("/api/auth/admin/login", headers=ORIGIN,
                                  json={"email": staff.email, "password": PASSWORD})
        assert login.status_code == 200
    return staff, learner


async def _grant(client, learner_id, tier="plus", days=30, reason="goodwill after an outage", headers=ORIGIN):
    return await client.post(f"/api/admin/users/{learner_id}/subscription", headers=headers,
                             json={"tier": tier, "days": days, "reason": reason})


async def _revoke(client, learner_id, reason="granted by mistake", headers=ORIGIN):
    return await client.post(f"/api/admin/users/{learner_id}/subscription/revoke", headers=headers,
                             json={"reason": reason})


async def test_overview_counts_plans_and_paid_orders_of_this_month(client, db_session):
    _, learner = await _people(db_session, client)
    other = User(full_name="Other", email="other@example.com", password_hash="x")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Subscription(user_id=learner.id, tier="pro", expires_at=now + timedelta(days=10)),
        Subscription(user_id=other.id, tier="plus", expires_at=now - timedelta(days=1)),  # ran out: free again
        Order(user_id=learner.id, plan_code="pro_monthly", amount=199_000, status="paid", paid_at=now),
        Order(user_id=other.id, plan_code="plus_monthly", amount=99_000, status="paid",
              paid_at=now - timedelta(days=70)),
        Order(user_id=other.id, plan_code="plus_monthly", amount=99_000, status="pending"),
        Order(user_id=other.id, plan_code="plus_monthly", amount=99_000, status="paid_unapplied", paid_at=now),
    ])
    await db_session.commit()

    body = (await client.get("/api/admin/overview")).json()
    assert body["plan_counts"] == {"free": 1, "plus": 0, "pro": 1}
    assert (body["orders_paid_total"], body["revenue_total"]) == (2, 298_000)
    assert (body["orders_paid_this_month"], body["revenue_this_month"]) == (1, 199_000)


async def test_learner_billing_shows_the_plan_and_orders(client, db_session):
    _, learner = await _people(db_session, client)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Subscription(user_id=learner.id, tier="plus", expires_at=now + timedelta(days=30)),
        Order(user_id=learner.id, plan_code="plus_monthly", amount=99_000, status="paid", paid_at=now,
              provider_txn_id=92704),
    ])
    await db_session.commit()

    r = await client.get(f"/api/admin/users/{learner.id}/billing")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert (body["tier"], body["days_left"]) == ("plus", 30)
    assert [(o["status"], o["amount"], o["provider_txn_id"]) for o in body["orders"]] == [("paid", 99_000, 92704)]
    listing = (await client.get("/api/admin/users")).json()
    assert listing["items"][0]["tier"] == "plus"


async def test_grant_then_revoke_changes_the_learners_plan_and_is_audited(client, db_session):
    staff, learner = await _people(db_session, client)
    granted = await _grant(client, learner.id, "pro", 7)
    assert granted.status_code == 200, granted.text
    assert (granted.json()["tier"], granted.json()["days_left"]) == ("pro", 7)

    token = (await client.post("/api/auth/login", json={"email": learner.email, "password": "password123"})
             ).json()["access_token"]
    me = (await client.get("/api/billing/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["tier"] == "pro" and me["entitlements"]["ciel_per_day"] == 200
    assert me["orders"] == []  # a gift is not a sale

    revoked = await _revoke(client, learner.id)
    assert revoked.status_code == 200 and revoked.json()["tier"] == "free"
    me = (await client.get("/api/billing/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["tier"] == "free"
    assert (await _revoke(client, learner.id)).status_code == 409  # nothing left to end

    entries = (await db_session.execute(select(AdminAuditLog).where(AdminAuditLog.target_user_id == learner.id)
                                        .order_by(AdminAuditLog.id))).scalars().all()
    assert [(e.action, e.actor_user_id, e.detail) for e in entries] == [
        ("subscription_granted", staff.id, "pro 7d: goodwill after an outage"),
        ("subscription_revoked", staff.id, "pro: granted by mistake"),
    ]
    mine = (await client.get("/api/admin/audit/me?action=subscription_granted")).json()
    assert mine["total"] == 1 and mine["items"][0]["target_user_id"] == learner.id


async def test_grant_replaces_the_running_plan(client, db_session):
    _, learner = await _people(db_session, client)
    db_session.add(Subscription(user_id=learner.id, tier="plus",
                                expires_at=datetime.now(timezone.utc) + timedelta(days=200)))
    await db_session.commit()
    body = (await _grant(client, learner.id, "pro", 30)).json()
    assert (body["tier"], body["days_left"]) == ("pro", 30)


@pytest.mark.parametrize("payload", [
    {"tier": "free", "days": 30, "reason": "valid reason"},
    {"tier": "gold", "days": 30, "reason": "valid reason"},
    {"tier": "plus", "days": 0, "reason": "valid reason"},
    {"tier": "plus", "days": 367, "reason": "valid reason"},
    {"tier": "plus", "days": 30, "reason": "  "},
    {"tier": "plus", "days": 30},
])
async def test_grant_rejects_bad_input(client, db_session, payload):
    _, learner = await _people(db_session, client)
    r = await client.post(f"/api/admin/users/{learner.id}/subscription", headers=ORIGIN, json=payload)
    assert r.status_code == 422
    assert (await db_session.execute(select(Subscription))).scalars().first() is None


async def test_only_a_signed_in_admin_from_our_origin_can_change_plans(client, db_session):
    staff, learner = await _people(db_session, client, sign_in=False)
    assert (await _grant(client, learner.id)).status_code == 401
    assert (await client.get(f"/api/admin/users/{learner.id}/billing")).status_code == 401

    token = (await client.post("/api/auth/login", json={"email": learner.email, "password": "password123"})
             ).json()["access_token"]
    as_learner = {**ORIGIN, "Authorization": f"Bearer {token}"}
    assert (await _grant(client, learner.id, headers=as_learner)).status_code == 401  # a learner token is not a session

    assert (await client.post("/api/auth/admin/login", headers=ORIGIN,
                              json={"email": staff.email, "password": PASSWORD})).status_code == 200
    assert (await _grant(client, learner.id, headers={})).status_code == 403
    assert (await _grant(client, learner.id, headers={"Origin": "https://evil.example"})).status_code == 403
    assert (await _revoke(client, learner.id, headers={})).status_code == 403
    assert (await _grant(client, staff.id)).status_code == 404  # staff have no plan
    assert (await _grant(client, 999_999)).status_code == 404
    assert (await client.get(f"/api/admin/users/{staff.id}/billing")).status_code == 404
    assert (await db_session.execute(select(Subscription))).scalars().first() is None
