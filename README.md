# CodeProve Backend

AI-powered programming assessment API built with FastAPI.

> **Running the full stack?** See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for step-by-step instructions covering the database, backend, and frontend - including the end-to-end Definition of Done checklist.

## Quick start (backend only)

```bash
# 1. Configure environment
cp .env.example .env   # then fill POSTGRES_PASSWORD (+ DATABASE_URL), JWT_SECRET, OPENAI_API_KEY

# 2. Start Postgres (bound to 127.0.0.1:5432 only)
docker compose up -d db

# 3. Create venv and install deps
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

# 4. Migrate + seed
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.seed.exercises_seed

# 5. Run
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Configuration notes

- `CORS_ORIGINS` is a comma-separated list of allowed origins, e.g.
  `CORS_ORIGINS=http://localhost:3000,http://localhost:5173`
  (plain strings, not JSON).
- If `POSTGRES_PASSWORD` contains URL-reserved characters, set
  `POSTGRES_PASSWORD_URLENCODED` to its URL-encoded form. Leave the original
  `POSTGRES_PASSWORD` unchanged; Docker Compose uses the encoded copy only in
  the backend database URL. Use the encoded copy in the host-side `DATABASE_URL`
  too if running Alembic or Python outside Docker.

### Internal admin accounts

After applying migrations, run `python -m scripts.bootstrap_admins` from the backend root
with the same database configuration. It creates Trung as `super_admin` and Kiet,
Phat, Minh as `admin`; existing matching accounts are left untouched. The command
prints a different random temporary password **once** for each new account.
Deliver each credential privately. Do not paste passwords into Git, `.env`, or logs.
The email-shaped IDs are internal login IDs and require no mailbox. On first login,
each admin must set a new password. If a regular admin forgets it, the super admin
issues a new temporary password from `/admin/admins`; the old sessions are revoked.

Admin auth uses a separate HttpOnly cookie. The frontend proxies admin requests
through its own `/api/admin-gateway` route, so the default `lax` cookie works
even when the API is on another site. Set `FRONTEND_URL` and `CORS_ORIGINS`
to the actual frontend origin, and set `NEXT_PUBLIC_API_URL` on the frontend
to the backend origin. The current login throttle is process-local, so deploy a shared
rate limiter before running multiple backend workers. MFA for the super admin is
planned for a later phase.

### Admin exercise workflow

Apply the latest migration (`alembic upgrade head`) before using these endpoints.
Every route below requires a current admin session and a changed temporary password;
write routes also require the configured frontend `Origin`. The frontend uses the
same-origin admin gateway. New exercises remain invisible to learners until publish.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/admin/exercises` | Search and paginate published exercises and drafts. |
| `GET /api/admin/exercises/{code}` | Read the current draft, or a snapshot of a published exercise. Includes private tests and reference code for admins. |
| `POST /api/admin/exercises/drafts` | Create a new exercise draft (no learner exercise row yet). |
| `POST /api/admin/exercises/{code}/draft` | Start editing an existing published exercise. |
| `PUT /api/admin/exercises/drafts/{code}` | Save changed fields using `expected_revision` to prevent stale writes. |
| `POST /api/admin/exercises/drafts/{code}/validate` | Run the existing content validator and return errors without changing state. |
| `POST /api/admin/exercises/drafts/{code}/submit` | Validate, then send a draft for review. |
| `POST /api/admin/exercises/drafts/{code}/approve` | Approve as a different admin from the last editor. |
| `POST /api/admin/exercises/drafts/{code}/reject` | Return a submitted draft to editing, as a different admin. |
| `POST /api/admin/exercises/drafts/{code}/publish` | Revalidate and atomically update the learner exercise and tests. |
| `GET /api/admin/audit` | Super admin only; includes authoring actions and `target_exercise_code`. Supports `actor_id`, `action`, and `exercise_code` filters. |

Each workflow action records its actor, exercise code, revision, and for edits the
names of changed fields. Audit entries never contain solutions or hidden test data.
Publishing changes an exercise's `content_source` to `admin`; the legacy file sync
skips it thereafter to avoid overwriting an admin-published version. Do not edit
that exercise via `content/exercises/*.json` after transferring it to admin review.
The exercise editor persists drafts in the database. The file-based sync remains
available for exercises that have not entered the admin workflow.

### Code sandbox security

User code (`/api/attempts/{id}/run`, `/api/practice/trace`) runs in a child
process with a scrubbed environment, a private scratch dir, rlimits (Linux)
and, inside the Docker image, as the unprivileged `sandbox` user. Both endpoints
require login and are rate limited (`SANDBOX_RATE_LIMIT_PER_MINUTE`). This is
not full isolation: the child still has network access. See the docstring in
`app/features/sandbox/runner.py` for the follow-up (dedicated sandbox container).

## Testing

```bash
pytest
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```
