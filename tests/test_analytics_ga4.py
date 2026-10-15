from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.features.analytics import ga4
from app.features.auth import service as auth_service
from app.models import Order, User
from tests.test_billing_checkout import AUTH, sepay, webhook_body  # noqa: F401  (fixture)

GA_IDS = {"ga_client_id": "1234567890.1728990000", "ga_session_id": 1728990123}


@pytest.fixture
def ga(monkeypatch, sepay):  # noqa: F811
    """GA4 configured, with every purchase captured instead of sent."""
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST123")
    monkeypatch.setenv("GA_API_SECRET", "secret")
    get_settings.cache_clear()
    sent: list[dict] = []

    async def fake_send(payload: dict) -> bool:
        sent.append(payload)
        return True

    monkeypatch.setattr(ga4, "send_purchase", fake_send)
    yield sent
    get_settings.cache_clear()


async def _checkout(client, headers, **extra):
    r = await client.post("/api/billing/checkout", json={"plan_code": "plus_monthly", **extra}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["order_id"]


async def _order(db_session, order_id: int) -> Order:
    db_session.expire_all()
    return (await db_session.execute(select(Order).where(Order.id == order_id))).scalar_one()


# --- checkout keeps the buyer's GA ids --------------------------------------------------------

async def test_checkout_saves_ga_ids(client, db_session, auth_headers, ga):
    order = await _order(db_session, await _checkout(client, auth_headers, **GA_IDS))
    assert (order.ga_client_id, order.ga_session_id) == (GA_IDS["ga_client_id"], GA_IDS["ga_session_id"])


async def test_checkout_drops_malformed_ga_ids_instead_of_failing(client, db_session, auth_headers, ga):
    order_id = await _checkout(client, auth_headers, ga_client_id="<script>", ga_session_id="abc")
    order = await _order(db_session, order_id)
    assert order.ga_client_id is None and order.ga_session_id is None


async def test_checkout_accepts_session_id_as_text(client, db_session, auth_headers, ga):
    order = await _order(db_session, await _checkout(client, auth_headers, ga_client_id=GA_IDS["ga_client_id"],
                                                     ga_session_id="1728990123"))
    assert order.ga_session_id == 1728990123


async def test_reused_pending_order_takes_the_latest_visit(client, db_session, auth_headers, ga):
    first = await _checkout(client, auth_headers)
    again = await _checkout(client, auth_headers, **GA_IDS)
    assert first == again
    assert (await _order(db_session, again)).ga_client_id == GA_IDS["ga_client_id"]


# --- the paid webhook reports the purchase ----------------------------------------------------

async def test_paid_webhook_reports_one_purchase(client, db_session, auth_headers, ga):
    order_id = await _checkout(client, auth_headers, **GA_IDS)
    body = webhook_body(order_id, 99_000)
    assert (await client.post("/api/billing/webhook", json=body, headers=AUTH)).status_code == 200
    assert (await client.post("/api/billing/webhook", json=body, headers=AUTH)).status_code == 200  # resend

    assert len(ga) == 1
    payload = ga[0]
    assert payload["client_id"] == GA_IDS["ga_client_id"]
    event = payload["events"][0]
    assert event["name"] == "purchase"
    assert event["params"]["transaction_id"] == f"CP{order_id}"
    assert event["params"]["value"] == 99_000 and event["params"]["currency"] == "VND"
    assert event["params"]["session_id"] == GA_IDS["ga_session_id"]
    assert event["params"]["items"] == [{"item_id": "plus_monthly", "item_name": "Plus", "item_variant": "monthly",
                                         "price": 99_000, "quantity": 1}]


async def test_wrong_amount_is_not_reported(client, auth_headers, ga):
    order_id = await _checkout(client, auth_headers, **GA_IDS)
    await client.post("/api/billing/webhook", json=webhook_body(order_id, 1_000), headers=AUTH)
    assert ga == []


async def test_nothing_is_reported_when_ga_is_off(client, auth_headers, sepay, monkeypatch):  # noqa: F811
    called = []
    monkeypatch.setattr(ga4, "send_purchase", lambda payload: called.append(payload))
    order_id = await _checkout(client, auth_headers, **GA_IDS)
    r = await client.post("/api/billing/webhook", json=webhook_body(order_id, 99_000), headers=AUTH)
    assert r.status_code == 200 and called == []


# --- payload and sending ----------------------------------------------------------------------

def test_payload_without_browser_ids_still_counts_the_purchase(sepay):  # noqa: F811
    order = Order(id=7, user_id=42, plan_code="pro_yearly", amount=1_990_000, status="paid",
                  paid_at=datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc))
    payload = ga4.purchase_payload(order)
    assert payload["client_id"] == "server.42"
    assert payload["timestamp_micros"] == int(order.paid_at.timestamp() * 1_000_000)
    params = payload["events"][0]["params"]
    assert "session_id" not in params
    assert params["items"][0]["item_name"] == "Pro" and params["items"][0]["item_variant"] == "yearly"


async def test_send_purchase_posts_to_measurement_protocol(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST123")
    monkeypatch.setenv("GA_API_SECRET", "secret")
    get_settings.cache_clear()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(204)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(ga4.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    payload = {"client_id": "1.2", "events": [{"name": "purchase", "params": {"transaction_id": "CP1"}}]}
    assert await ga4.send_purchase(payload) is True
    url = urlsplit(seen["url"])
    assert url.netloc == "www.google-analytics.com" and url.path == "/mp/collect"
    assert parse_qs(url.query) == {"measurement_id": ["G-TEST123"], "api_secret": ["secret"]}
    get_settings.cache_clear()


async def test_send_purchase_never_raises(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST123")
    monkeypatch.setenv("GA_API_SECRET", "secret")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(ga4.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    payload = {"client_id": "1.2", "events": [{"name": "purchase", "params": {"transaction_id": "CP1"}}]}
    assert await ga4.send_purchase(payload) is False
    get_settings.cache_clear()


# --- Google sign-in tells the frontend about new accounts -------------------------------------

@pytest.mark.parametrize("created", [True, False])
async def test_google_callback_flags_new_accounts(client, db_session, monkeypatch, created):
    user = (await db_session.execute(select(User))).scalars().first()
    if user is None:
        user = User(full_name="Lan", email="lan@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()

    async def fake_auth(_db, _code):
        return user, created

    monkeypatch.setattr(auth_service, "authenticate_google", fake_auth)
    state = auth_service.create_oauth_state(None)
    r = await client.get("/api/auth/google/callback", params={"code": "c", "state": state})
    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert "token" in query
    assert query.get("new_user") == (["1"] if created else None)
