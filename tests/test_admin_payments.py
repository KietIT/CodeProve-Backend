"""Admins see every incoming transfer and chart-ready payment totals."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.models import Order, PaymentEvent, User

pytestmark = pytest.mark.asyncio

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "temporary-password-2026"


async def _people(db_session, client, *, sign_in=True) -> User:
    staff = User(full_name="Staff", email="staff@codeprove.production", password_hash=hash_password(PASSWORD),
                 role="admin", must_change_password=False)
    learner = User(full_name="Linh Tran", email="linh@example.com", password_hash=hash_password("password123"))
    db_session.add_all([staff, learner])
    await db_session.commit()
    await db_session.refresh(learner)
    if sign_in:
        login = await client.post("/api/auth/admin/login", headers=ORIGIN,
                                  json={"email": staff.email, "password": PASSWORD})
        assert login.status_code == 200
    return learner


def _event(order_id, amount, txn_id, received_at, *, transfer_type="in", valid=True, processed=True) -> PaymentEvent:
    raw = {"id": txn_id, "gateway": "TPBank", "content": f"MBVCB.1.CP{order_id}.CT tu 111 TRAN LINH",
           "transferType": transfer_type, "transferAmount": amount, "accountNumber": "0123456789",
           "referenceCode": f"FT{txn_id}", "transactionDate": "2026-10-28 10:15:30"}
    return PaymentEvent(order_id=order_id, provider_txn_id=txn_id, raw=raw, signature_valid=valid,
                        processed=processed, received_at=received_at)


async def test_history_lists_only_codeprove_transfers_newest_first(client, db_session):
    learner = await _people(db_session, client)
    now = datetime.now(timezone.utc)
    order = Order(user_id=learner.id, plan_code="plus_monthly", amount=99_000, status="paid", paid_at=now)
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    db_session.add_all([
        _event(order.id, 99_000, 1, now - timedelta(hours=2)),
        _event(None, 50_000, 2, now - timedelta(hours=1), processed=False),  # personal money: no order code
        _event(999, 70_000, 5, now - timedelta(hours=1)),  # a code-like text, but no such order
        _event(order.id, 99_000, 3, now, transfer_type="out"),  # money out: not listed
        _event(order.id, 99_000, 4, now, valid=False),  # unsigned call: not listed
    ])
    await db_session.commit()

    response = await client.get("/api/admin/payments")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["total"] == 1
    (matched,) = body["items"]
    assert matched["user_name"] == "Linh Tran" and matched["user_email"] == "linh@example.com"
    assert (matched["amount"], matched["bank"], matched["plan_code"], matched["order_status"]) == (
        99_000, "TPBank", "plus_monthly", "paid")
    assert (matched["account_number"], matched["reference_code"], matched["transaction_date"]) == (
        "0123456789", "FT1", "2026-10-28 10:15:30")
    assert "CP" in matched["transfer_content"]

    found = (await client.get("/api/admin/payments", params={"search": "LINH@"})).json()
    assert [item["provider_txn_id"] for item in found["items"]] == [1]
    assert (await client.get("/api/admin/payments", params={"search": "nobody"})).json()["total"] == 0


async def test_summary_fills_every_day_and_adds_up_money(client, db_session):
    learner = await _people(db_session, client)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Order(user_id=learner.id, plan_code="plus_monthly", amount=99_000, status="paid", paid_at=now),
        Order(user_id=learner.id, plan_code="pro_monthly", amount=199_000, status="paid", paid_at=now),
        Order(user_id=learner.id, plan_code="plus_monthly", amount=99_000, status="paid",
              created_at=now - timedelta(days=90), paid_at=now - timedelta(days=90)),  # outside the window
        Order(user_id=learner.id, plan_code="plus_monthly", amount=99_000, status="pending"),
        Order(user_id=learner.id, plan_code="plus_yearly", amount=990_000, status="paid_unapplied", paid_at=now),
    ])
    db_session.add(_event(None, 50_000, 9, now, processed=False))
    await db_session.commit()

    response = await client.get("/api/admin/payments/summary", params={"days": 7})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["by_day"]) == 7
    assert body["revenue"] == 99_000 + 199_000 + 990_000
    assert body["paid_orders"] == 3
    assert body["average_order"] == body["revenue"] // 3
    assert sum(day["revenue"] for day in body["by_day"]) == body["revenue"]
    assert {slice_["plan_code"]: slice_["orders"] for slice_ in body["by_plan"]} == {
        "plus_monthly": 1, "pro_monthly": 1, "plus_yearly": 1}
    assert {slice_["status"]: slice_["orders"] for slice_ in body["by_status"]} == {
        "paid": 2, "pending": 1, "paid_unapplied": 1}
    assert body["transfers_received"] == 0  # the one transfer here matches no order, so it is not ours
    assert "needs_attention" not in body


async def test_summary_rejects_a_bad_window_and_empty_data_is_zero(client, db_session):
    await _people(db_session, client)
    assert (await client.get("/api/admin/payments/summary", params={"days": 0})).status_code == 422
    body = (await client.get("/api/admin/payments/summary")).json()
    assert (body["revenue"], body["paid_orders"], body["average_order"]) == (0, 0, 0)
    assert len(body["by_day"]) == 30


async def test_payments_need_a_ready_admin(client, db_session):
    await _people(db_session, client, sign_in=False)
    for path in ("/api/admin/payments", "/api/admin/payments/summary"):
        assert (await client.get(path)).status_code == 401
