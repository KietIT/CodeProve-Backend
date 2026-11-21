# Auth API: phone at signup, login by email or phone

## Phone format

Vietnamese mobile numbers only: 10 digits, `0` + network prefix `3`, `5`, `7`, `8` or `9`.
The server accepts `0912345678`, `+84912345678`, `84912345678` and the same with spaces, dots,
dashes or brackets, and stores the canonical `0912345678`. Anything else → `422`.
A phone number belongs to one account only.

## `POST /api/auth/signup`

`phone` is now **required**.

```json
{ "full_name": "Lan Nguyen", "email": "lan@test.io", "phone": "0912 345 678",
  "password": "password123", "accept_privacy": true }
```

| Status | When | `detail` |
|---|---|---|
| 200 | created | `AuthOut` (below) |
| 409 | email taken | `"Email already registered"` |
| 409 | phone taken | `"Phone number already registered"` |
| 422 | phone missing or not a Vietnamese mobile number | pydantic error on `phone` |

## `POST /api/auth/login`

The login ID is an email **or** a phone number, sent as `identifier`. If it contains `@` it is
treated as an email, otherwise as a phone number. The old `email` key is still accepted with the
same meaning, so current clients keep working.

```json
{ "identifier": "0912345678", "password": "password123" }
```

| Status | When | `detail` |
|---|---|---|
| 200 | ok | `AuthOut` |
| 401 | no such account, wrong password, staff or disabled account | `"Invalid email, phone number or password"` |
| 422 | identifier is neither an email nor a valid phone number | pydantic error on `identifier` |

## `PATCH /api/auth/me`

Accepts an optional `phone` so accounts without one (created before this change, or via Google)
can add one and then log in with it. `409 "Phone number already registered"` if another account
has it; `422` if invalid.

## `UserOut` / `AuthOut`

`UserOut` gains `phone: string | null` (null for older and Google accounts).

```json
{ "user": { "id": 1, "full_name": "Lan Nguyen", "email": "lan@test.io",
            "phone": "0912345678", "avatar": null },
  "access_token": "..." }
```

Google sign-in is unchanged and creates accounts without a phone.
The admin login (`POST /api/auth/admin/login`) stays email-only.
