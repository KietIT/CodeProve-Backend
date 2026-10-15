# Google Analytics 4 and UTM

Source: the team guide `CodeProve_Huong_dan_GA4_UTM.pdf` (Marketing). It measures the three CAP numbers, visits,
sign-ups and paying users, split by channel (TikTok, Facebook...) through UTM links. This page is what the code does
and what each person still has to do.

## Who sends which event

| Event | Sent by | When |
|---|---|---|
| `page_view` | Browser (gtag, Enhanced measurement) | Every page, including client-side route changes |
| `sign_up` `{method: "email"}` | Browser | `POST /api/auth/signup` answered OK, before going to the dashboard |
| `sign_up` `{method: "google"}` | Browser | `/auth/callback?token=...&new_user=1`. The backend adds `new_user=1` only when this Google sign-in created the account, so returning users are not counted again |
| `purchase` | **Backend** (Measurement Protocol) | The SePay webhook activates the order. See below |
| `challenge_complete` `{level}` (optional) | Browser | A submission is accepted |

### Why the backend sends `purchase`

Payment is a bank transfer. The money can arrive minutes later, after the buyer has closed `/billing/pay`, so a
purchase fired from the browser would be lost. At checkout the frontend sends the buyer's GA `client_id` and
`session_id` (`POST /api/billing/checkout`, see `docs/api/billing.md`). They are stored on the order
(`orders.ga_client_id`, `orders.ga_session_id`). When the webhook marks the order `paid`, the backend posts the
`purchase` to GA under those ids, so GA credits the visit (and its UTM source) that brought the buyer.

- `transaction_id` is the payment code `CP<order id>`, so a repeat is dropped by GA and the line can be matched
  to the bank statement.
- No name, email or user id is sent. `non_personalized_ads` is set.
- If the browser ids are missing (analytics blocked), the purchase is still sent with `client_id`
  `server.<user id>`. It counts in revenue, but under source `(not set)`.
- GA being down or misconfigured never affects the payment: the call runs after SePay gets its answer, has a
  5 s timeout, and failures are only logged (`GA4 purchase CP12 not sent/rejected`).
- `coupon` is not sent: there are no discount codes yet. CAP Test 3 (EARLY30 vs NHOM3) needs a coupon feature
  first.

## Setup

**Marketing (GA4):**
1. Create the property and web stream (guide part 1). Give the Measurement ID `G-...` to Frontend and Backend.
2. Admin > Data streams > CodeProve Web > **Measurement Protocol API secrets** > Create. Give the secret to the
   backend owner only (it goes in the EC2 `.env`, never in git or chat).
3. Admin > Data collection: keep **Google signals off**. The privacy policy says advertising features are off.
4. After the first `sign_up` and `purchase` arrive: Admin > Events > **Mark as key event** for both.
5. Data retention 14 months, unwanted referrals, internal traffic filter (guide part 4). SePay pays by bank
   transfer, so no payment-gateway domain redirects back: unwanted referrals are only needed if a gateway is added.

**Backend (EC2):**
1. `.env`: `GA_MEASUREMENT_ID=G-...` and `GA_API_SECRET=...`.
2. `docker compose up -d --build` (runs migration `d9b2f4a6c8e1`, two nullable columns on `orders`).

**Frontend (Vercel):** `NEXT_PUBLIC_GA_ID=G-...` for Production, then redeploy. Code changes are in the
CodeProve-UI repo.

**Domains:** in Vercel, make `code-prove.io.vn` and the old `*.vercel.app` URL redirect to
`https://www.code-prove.io.vn`. Also add `https://www.code-prove.io.vn` to the backend `CORS_ORIGINS` and the
Google OAuth origins if it is not there yet.

## Privacy

Policy version **2026-10-3** (`docs/legal/chinh-sach-quyen-rieng-tu.md`) adds Google Analytics and SePay. Every
user is asked to accept it again before using the AI features. The frontend shows the same text on `/privacy`.

## Checking it works

1. Open `https://www.code-prove.io.vn/?utm_source=test&utm_medium=test` on a phone (4G, no ad blocker).
   GA4 > Reports > Realtime shows 1 active user, source `test`.
2. Sign up a test account: Realtime > Event count shows `sign_up`.
3. Buy a plan with a real transfer (the money lands in the team account). Within a minute of the webhook:
   Realtime shows `purchase`. Backend log has no `GA4 purchase ... not sent` line.
4. Nothing shows: redeployed? right Measurement ID? ad blocker off? In DevTools > Network, filter `collect`.
