from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.features.billing import entitlements, service
from app.models import Order, Subscription, User


async def _user_id(db_session) -> int:
    return (await db_session.execute(select(User))).scalars().first().id


async def test_plans_are_listed_with_server_prices(client):
    r = await client.get("/api/billing/plans")
    assert r.status_code == 200
    prices = {p["code"]: (p["amount"], p["days"]) for p in r.json()}
    assert prices == {
        "plus_monthly": (99_000, 30),
        "plus_yearly": (990_000, 365),
        "pro_monthly": (199_000, 30),
        "pro_yearly": (1_990_000, 365),
    }


async def test_me_requires_login(client):
    assert (await client.get("/api/billing/me")).status_code == 401


async def test_new_user_is_free(client, auth_headers):
    body = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert body["tier"] == "free"
    assert body["expires_at"] is None and body["days_left"] == 0
    assert body["entitlements"]["ciel_per_day"] == 20
    assert body["entitlements"]["monthly_submits"] == 10
    assert body["orders"] == []


async def test_active_subscription_sets_tier_and_days_left(client, db_session, auth_headers):
    uid = await _user_id(db_session)
    db_session.add(Subscription(user_id=uid, tier="plus", expires_at=datetime.now(timezone.utc) + timedelta(days=10, hours=1)))
    await db_session.commit()
    body = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert body["tier"] == "plus"
    assert body["days_left"] == 11
    assert body["entitlements"]["ciel_per_day"] == 100
    assert body["entitlements"]["monthly_submits"] is None


async def test_expired_subscription_falls_back_to_free(client, db_session, auth_headers):
    uid = await _user_id(db_session)
    db_session.add(Subscription(user_id=uid, tier="pro", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    await db_session.commit()
    assert await service.current_tier(db_session, uid) == "free"
    body = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert body["tier"] == "free" and body["days_left"] == 0


async def test_orders_are_listed_newest_first(client, db_session, auth_headers):
    uid = await _user_id(db_session)
    db_session.add_all([
        Order(user_id=uid, plan_code="plus_monthly", amount=99_000, status="expired"),
        Order(user_id=uid, plan_code="pro_monthly", amount=199_000, status="pending"),
    ])
    await db_session.commit()
    orders = (await client.get("/api/billing/me", headers=auth_headers)).json()["orders"]
    assert [o["plan_code"] for o in orders] == ["pro_monthly", "plus_monthly"]


def test_entitlements_per_tier():
    assert [entitlements.for_tier(t).ciel_per_day for t in ("free", "plus", "pro")] == [20, 100, 200]
    assert entitlements.for_tier("pro").learning_path and not entitlements.for_tier("plus").learning_path
    assert entitlements.for_tier("unknown").tier == "free"
