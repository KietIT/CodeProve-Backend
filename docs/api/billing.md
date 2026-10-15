# Billing API (SePay)

Prices and benefits live in `app/features/billing/plans.py` and `entitlements.py`. A plan is bought for one
period (30 or 365 days); there is no auto-renewal.

Payment is a **bank transfer**: the student sends the order's exact amount to our bank account with the order's
payment code (`CP<order id>`) as the transfer content. [SePay](https://sepay.vn) watches the account and calls
our webhook when the money arrives. There is no hosted payment page: the frontend shows the QR and the details.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/billing/plans` | none | The four plans: `plus_monthly`, `plus_yearly`, `pro_monthly`, `pro_yearly`. |
| `GET /api/billing/me` | learner | `tier`, `expires_at`, `days_left`, `entitlements`, last 50 `orders`. |
| `POST /api/billing/checkout` | learner | Body `{"plan_code", "ga_client_id"?, "ga_session_id"?}` -> payment details (below). Show them on `/billing/pay?order={id}`. |
| `GET /api/billing/orders/{id}/payment` | learner | The same payment details for an existing order (page reload). |
| `POST /api/billing/orders/{id}/cancel` | learner | Cancel an order that is still `pending`. |
| `POST /api/billing/webhook` | SePay API key | Only this call activates a plan. |

Payment details: `{order_id, status, plan_code, amount, payment_code, bank_name, account_number, account_name,
qr_url, expires_at}`. `qr_url` is a VietQR image with the account, amount and content filled in.

Checkout errors (`detail.code`): `unknown_plan` (404), `payments_not_configured` (503),
`plan_change_not_allowed` (409, carries `current_tier` and `expires_at`: wait for the running plan to end, then
buy the other one; buying the same tier again extends it), rate limit (429). Asking again for the same plan while
an order is `pending` returns that order.

The payment page must **poll `GET /api/billing/me`** until the order is `paid`; nothing in the browser proves a
payment.

**Analytics.** The frontend does **not** send the GA4 `purchase` event: the backend sends it when the webhook
activates the order (Measurement Protocol, `app/features/analytics/ga4.py`), so it is counted even if the buyer
closed the page. For GA to credit the right channel, checkout should carry the browser's GA ids from
`gtag('get', NEXT_PUBLIC_GA_ID, 'client_id' | 'session_id', cb)`. Both are optional; a malformed value is dropped,
never rejected. The purchase uses `transaction_id` = the payment code (`CP<order id>`), `value` = amount,
`currency` = `VND` and one item (`item_id` = plan code, `item_name` = `Plus`/`Pro`, `item_variant` = period).
Only `paid` orders are reported (not `paid_unapplied`). Setup and the rest of GA4: `docs/analytics/ga4.md`.

Order statuses: `pending`, `paid`, `cancelled`, `expired` (unpaid after `PAYMENT_WINDOW_MINUTES`),
`paid_unapplied` (paid while a different tier was running: support resolves it), `refunded`. A transfer that
arrives for an `expired` or `cancelled` order is still honoured.

Webhook rules: the `Authorization: Apikey <SEPAY_API_KEY>` header must match (else 401), the transfer must be
incoming (`transferType = "in"`), the order id is read from SePay's `code` or else from `content`, and
`transferAmount` must equal the order's amount. A resend changes nothing; a second transfer for a paid order is
recorded but not applied. Every webhook is stored in `payment_events`. Valid calls always get
`200 {"success": true}` (SePay retries anything else).

## What each plan changes (enforced in the backend)

| | Free | Plus | Pro |
|---|---|---|---|
| Ciel messages per day | `CIEL_PER_DAY` (20) | `CIEL_PER_DAY_PLUS` (100) | `CIEL_PER_DAY_PRO` (200) |
| Submissions per month | `FREE_SUBMITS_PER_MONTH` (10) | unlimited | unlimited |

Going over a limit answers **429** with `detail = {code, message_vi, message_en, tier, upgrade}`:
`ciel_daily_limit` (Ciel) or `monthly_submit_limit` (`POST /api/attempts/{id}/submit`). `upgrade` is true when a
higher plan would lift the limit, so the UI can show an upgrade offer. The "month" is the calendar month in
`QUOTA_TIMEZONE`; an attempt already submitted this month is not counted twice. `GET /api/billing/me` returns the
current limits under `entitlements`. `detailed_analysis` and `learning_path` flags exist there but are **not
enforced yet**.

Giving or ending a plan without payment (goodwill, or after support decides): an admin does it on the learner's
page in the admin area (`POST /api/admin/users/{id}/subscription`, `.../subscription/revoke`), which writes the
audit log. `python -m scripts.grant_plan <email> plus|pro|free [days]` does the same from a terminal, unaudited.
A plan given this way replaces the running one and creates no order, so it is not counted as revenue.

## Setup

1. In https://my.sepay.vn link the bank account that receives the money (e.g. TPBank).
2. `.env`: `SEPAY_BANK_ACCOUNT`, `SEPAY_BANK_NAME` (short name, e.g. `TPBank`), `SEPAY_ACCOUNT_NAME`, and
   `SEPAY_API_KEY` = a long random string you make up. Never commit them.
3. `alembic upgrade head`.
4. Expose the backend over HTTPS (production domain, or `cloudflared tunnel --url http://localhost:8000` for
   local testing). In SePay add a webhook: event "money in", that bank account, URL
   `https://<host>/api/billing/webhook`, authentication **API Key** with the same value as `SEPAY_API_KEY`.
5. In SePay's company settings set the payment-code prefix to `CP` (same as `SEPAY_CODE_PREFIX`) so SePay
   detects the code. Without it the backend still finds the code in the transfer content.
