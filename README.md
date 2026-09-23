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
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed.exercises_seed

# 5. Run
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Configuration notes

- `CORS_ORIGINS` is a comma-separated list of allowed origins, e.g.
  `CORS_ORIGINS=http://localhost:3000,http://localhost:5173`
  (plain strings, not JSON).

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
