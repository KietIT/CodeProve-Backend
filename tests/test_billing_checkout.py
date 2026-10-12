from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.features.billing import sepay_client
from app.models import Order, PaymentEvent, Subscription, User

KEY = "test-webhook-key"
AUTH = {"Authorization": f"Apikey {KEY}"}


@pytest.fixture
def sepay(monkeypatch):
    """SePay configured with a test key and a test bank account."""
    monkeypatch.setenv("SEPAY_API_KEY", KEY)
    monkeypatch.setenv("SEPAY_BANK_ACCOUNT", "0123456789")
    monkeypatch.setenv("SEPAY_BANK_NAME", "TPBank")
    monkeypatch.setenv("SEPAY_ACCOUNT_NAME", "NGUYEN VAN A")
    monkeypatch.setenv("SEPAY_CODE_PREFIX", "CP")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def webhook_body(order_id: int, amount: int, *, txn_id=92704, transfer_type="in", code=True) -> dict:
    """A transfer as SePay reports it. `code=False`: SePay did not detect the code, only the content has it."""
    return {"id": txn_id, "gateway": "TPBank", "transactionDate": "2026-10-12 10:00:00",
            "accountNumber": "0123456789", "subAccount": None, "code": f"CP{order_id}" if code else None,
            "content": f"MBVCB.123456.CP{order_id}.CT tu 111 NGUYEN VAN B", "transferType": transfer_type,
            "description": "BankAPINotify", "transferAmount": amount, "accumulated": 1_000_000,
            "referenceCode": "FT26286123456"}


async def _user(db_session) -> User:
    return (await db_session.execute(select(User))).scalars().first()


async def _checkout(client, headers, plan="plus_monthly"):
    return await client.post("/api/billing/checkout", json={"plan_code": plan}, headers=headers)


async def _order(db_session, order_id=None) -> Order:
    q = select(Order) if order_id is None else select(Order).where(Order.id == order_id)
    return (await db_session.execute(q.order_by(Order.id.desc()))).scalars().first()


async def _hook(client, body, headers=AUTH):
    return await client.post("/api/billing/webhook", json=body, headers=headers)


async def _paid(client, db_session, headers, plan="plus_monthly", txn_id=92704):
    r = await _checkout(client, headers, plan)
    assert r.status_code == 200, r.text
    order = await _order(db_session, r.json()["order_id"])
    w = await _hook(client, webhook_body(order.id, order.amount, txn_id=txn_id))
    assert w.status_code == 200 and w.json() == {"success": True}
    return order


# --- client ------------------------------------------------------------------------------------

def test_verify_webhook_accepts_only_our_api_key(sepay):
    assert sepay_client.verify_webhook(f"Apikey {KEY}")
    assert sepay_client.verify_webhook(f"apikey  {KEY} ")
    assert not sepay_client.verify_webhook("Apikey wrong")
    assert not sepay_client.verify_webhook(f"Bearer {KEY}")
    assert not sepay_client.verify_webhook(KEY)
    assert not sepay_client.verify_webhook(None)


def test_verify_webhook_rejects_everything_without_a_key(monkeypatch):
    monkeypatch.setenv("SEPAY_API_KEY", "")
    get_settings.cache_clear()
    assert not sepay_client.verify_webhook("Apikey ")
    assert not sepay_client.verify_webhook("Apikey")
    get_settings.cache_clear()


def test_order_id_is_read_from_the_code_or_the_content(sepay):
    assert sepay_client.order_id_from({"code": "CP12", "content": "x"}) == 12
    assert sepay_client.order_id_from({"code": None, "content": "MBVCB.1.cp345.CT tu 9 NGUYEN VAN B"}) == 345
    assert sepay_client.order_id_from({"code": None, "content": "tien an trua"}) is None
    assert sepay_client.order_id_from({"content": 5}) is None


def test_payment_details_carry_the_account_amount_and_code(sepay):
    d = sepay_client.payment_details(7, 99_000)
    assert (d["bank_name"], d["account_number"], d["payment_code"], d["amount"]) == ("TPBank", "0123456789", "CP7", 99_000)
    assert d["qr_url"] == "https://qr.sepay.vn/img?acc=0123456789&bank=TPBank&amount=99000&des=CP7"


# --- checkout ----------------------------------------------------------------------------------

async def test_checkout_requires_login(client, sepay):
    assert (await client.post("/api/billing/checkout", json={"plan_code": "plus_monthly"})).status_code == 401


async def test_checkout_503_when_sepay_not_configured(client, auth_headers, monkeypatch):
    for name in ("SEPAY_API_KEY", "SEPAY_BANK_ACCOUNT", "SEPAY_BANK_NAME"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    r = await _checkout(client, auth_headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "payments_not_configured"
    get_settings.cache_clear()


async def test_checkout_unknown_plan(client, auth_headers, sepay):
    r = await _checkout(client, auth_headers, "gold_forever")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "unknown_plan"


async def test_checkout_creates_pending_order_with_server_price(client, db_session, auth_headers, sepay):
    r = await _checkout(client, auth_headers, "pro_yearly")
    assert r.status_code == 200
    out = r.json()
    order = await _order(db_session, out["order_id"])
    assert (order.status, order.amount, order.plan_code) == ("pending", 1_990_000, "pro_yearly")
    assert (out["amount"], out["payment_code"], out["status"]) == (1_990_000, f"CP{order.id}", "pending")
    assert (out["bank_name"], out["account_number"], out["account_name"]) == ("TPBank", "0123456789", "NGUYEN VAN A")
    assert f"des=CP{order.id}" in out["qr_url"] and "amount=1990000" in out["qr_url"]
    assert out["expires_at"]


async def test_checkout_ignores_client_supplied_amount(client, db_session, auth_headers, sepay):
    r = await client.post("/api/billing/checkout", json={"plan_code": "plus_monthly", "amount": 1},
                          headers=auth_headers)
    assert r.status_code == 200
    assert (await _order(db_session)).amount == 99_000


async def test_checkout_reuses_the_open_order_for_the_same_plan(client, auth_headers, sepay):
    first = (await _checkout(client, auth_headers)).json()
    second = (await _checkout(client, auth_headers)).json()
    assert first == second


async def test_checkout_after_cancel_makes_a_new_order(client, auth_headers, sepay):
    first = (await _checkout(client, auth_headers)).json()
    await client.post(f"/api/billing/orders/{first['order_id']}/cancel", headers=auth_headers)
    second = (await _checkout(client, auth_headers)).json()
    assert second["order_id"] != first["order_id"]


async def test_checkout_is_rate_limited(client, auth_headers, sepay):
    codes = [(await _checkout(client, auth_headers, p)).status_code
             for p in ["plus_monthly", "plus_yearly", "pro_monthly", "pro_yearly", "plus_monthly", "plus_yearly"]]
    assert codes[-1] == 429


async def test_stale_pending_order_expires_and_a_new_one_is_made(client, db_session, auth_headers, sepay):
    first = (await _checkout(client, auth_headers)).json()
    order = await _order(db_session, first["order_id"])
    order.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db_session.commit()
    second = (await _checkout(client, auth_headers)).json()
    assert second["order_id"] != first["order_id"]
    await db_session.refresh(order)
    assert order.status == "expired"


# --- payment details of an order ---------------------------------------------------------------

async def test_payment_details_of_my_order(client, auth_headers, sepay):
    made = (await _checkout(client, auth_headers)).json()
    r = await client.get(f"/api/billing/orders/{made['order_id']}/payment", headers=auth_headers)
    assert r.status_code == 200 and r.json() == made


async def test_payment_details_of_someone_elses_order_are_hidden(client, auth_headers, sepay):
    made = (await _checkout(client, auth_headers)).json()
    other = await client.post("/api/auth/signup", json={
        "full_name": "Other", "email": "other@example.com", "password": "password123", "accept_privacy": True})
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert (await client.get(f"/api/billing/orders/{made['order_id']}/payment", headers=headers)).status_code == 404


# --- no switching mid-term -----------------------------------------------------------------------

async def test_cannot_buy_a_different_tier_while_one_runs(client, db_session, auth_headers, sepay):
    await _paid(client, db_session, auth_headers, "plus_monthly")
    r = await _checkout(client, auth_headers, "pro_monthly")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "plan_change_not_allowed" and detail["current_tier"] == "plus"
    assert detail["expires_at"]


async def test_can_buy_the_other_tier_after_expiry(client, db_session, auth_headers, sepay):
    await _paid(client, db_session, auth_headers, "plus_monthly")
    sub = (await db_session.execute(select(Subscription))).scalars().first()
    sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()
    assert (await _checkout(client, auth_headers, "pro_monthly")).status_code == 200


# --- webhook -----------------------------------------------------------------------------------

async def test_webhook_rejects_a_wrong_or_missing_key_and_changes_nothing(client, db_session, auth_headers, sepay):
    order = (await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"]))
    body = webhook_body(order.id, order.amount)
    assert (await _hook(client, body, {"Authorization": "Apikey wrong"})).status_code == 401
    assert (await _hook(client, body, {})).status_code == 401
    await db_session.refresh(order)
    assert order.status == "pending"
    event = (await db_session.execute(select(PaymentEvent))).scalars().first()
    assert event.signature_valid is False


async def test_webhook_rejects_non_json(client, sepay):
    r = await client.post("/api/billing/webhook", content=b"not json",
                          headers={"content-type": "application/json", **AUTH})
    assert r.status_code == 400


async def test_webhook_activates_the_plan(client, db_session, auth_headers, sepay):
    order = await _paid(client, db_session, auth_headers, "plus_monthly")
    await db_session.refresh(order)
    assert order.status == "paid" and order.paid_at is not None and order.provider_txn_id == 92704
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["tier"] == "plus" and me["days_left"] == 30
    assert me["entitlements"]["ciel_per_day"] == 100


async def test_webhook_finds_the_order_in_the_content_when_sepay_detected_no_code(client, db_session, auth_headers,
                                                                                 sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    assert (await _hook(client, webhook_body(order.id, order.amount, code=False))).status_code == 200
    await db_session.refresh(order)
    assert order.status == "paid"


async def test_yearly_plan_adds_365_days(client, db_session, auth_headers, sepay):
    await _paid(client, db_session, auth_headers, "pro_yearly")
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["tier"] == "pro" and me["days_left"] == 365


async def test_replayed_webhook_is_applied_once(client, db_session, auth_headers, sepay):
    order = await _paid(client, db_session, auth_headers)
    body = webhook_body(order.id, order.amount)
    for _ in range(3):
        assert (await _hook(client, body)).status_code == 200
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["days_left"] == 30


async def test_second_transfer_for_a_paid_order_adds_nothing(client, db_session, auth_headers, sepay):
    order = await _paid(client, db_session, auth_headers)
    assert (await _hook(client, webhook_body(order.id, order.amount, txn_id=555))).status_code == 200
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["days_left"] == 30
    events = (await db_session.execute(select(PaymentEvent).order_by(PaymentEvent.id))).scalars().all()
    assert [e.processed for e in events] == [True, False]  # the extra money is on record for support


async def test_same_tier_renewal_adds_to_the_remaining_time(client, db_session, auth_headers, sepay):
    await _paid(client, db_session, auth_headers, "plus_monthly", txn_id=1)
    await _paid(client, db_session, auth_headers, "plus_monthly", txn_id=2)
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["tier"] == "plus" and me["days_left"] == 60


async def test_amount_mismatch_does_not_activate(client, db_session, auth_headers, sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    r = await _hook(client, webhook_body(order.id, 1_000))
    assert r.status_code == 200
    await db_session.refresh(order)
    assert order.status == "pending"
    assert (await db_session.execute(select(Subscription))).scalars().first() is None


async def test_outgoing_transfer_does_not_activate(client, db_session, auth_headers, sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    r = await _hook(client, webhook_body(order.id, order.amount, transfer_type="out"))
    assert r.status_code == 200
    await db_session.refresh(order)
    assert order.status == "pending"


async def test_transfer_that_is_not_for_an_order_is_acknowledged(client, sepay):
    body = webhook_body(1, 3000, code=False) | {"content": "tien an trua"}
    r = await _hook(client, body)
    assert r.status_code == 200 and r.json() == {"success": True}
    assert (await _hook(client, webhook_body(999_999, 3000))).status_code == 200  # no such order


async def test_late_payment_on_an_expired_order_still_activates(client, db_session, auth_headers, sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    order.status = "expired"
    await db_session.commit()
    await _hook(client, webhook_body(order.id, order.amount))
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["tier"] == "plus"


async def test_payment_for_another_tier_while_one_runs_is_not_applied(client, db_session, auth_headers, sepay):
    plus = await _order(db_session, (await _checkout(client, auth_headers, "plus_monthly")).json()["order_id"])
    pro = await _order(db_session, (await _checkout(client, auth_headers, "pro_monthly")).json()["order_id"])
    for n, o in enumerate((plus, pro)):  # both orders were opened before either was paid
        await _hook(client, webhook_body(o.id, o.amount, txn_id=100 + n))
    await db_session.refresh(pro)
    assert pro.status == "paid_unapplied"
    me = (await client.get("/api/billing/me", headers=auth_headers)).json()
    assert me["tier"] == "plus" and me["days_left"] == 30


# --- cancel ------------------------------------------------------------------------------------

async def test_cancel_pending_order(client, db_session, auth_headers, sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    r = await client.post(f"/api/billing/orders/{order.id}/cancel", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    again = await client.post(f"/api/billing/orders/{order.id}/cancel", headers=auth_headers)
    assert again.status_code == 409


async def test_cannot_cancel_someone_elses_order(client, db_session, auth_headers, sepay):
    order = await _order(db_session, (await _checkout(client, auth_headers)).json()["order_id"])
    other = await client.post("/api/auth/signup", json={
        "full_name": "Other", "email": "other@example.com", "password": "password123", "accept_privacy": True})
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert (await client.post(f"/api/billing/orders/{order.id}/cancel", headers=headers)).status_code == 404
