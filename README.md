# CodeProve Backend

AI-powered programming assessment API built with FastAPI.

> **Running the full stack?** See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for step-by-step instructions covering the database, backend, and frontend — including the end-to-end Definition of Done checklist.

## Quick start (backend only)

```bash
# 1. Start Postgres
docker compose up -d db

# 2. Create venv and install deps
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

# 3. Configure environment
cp .env.example .env   # then fill JWT_SECRET and OPENAI_API_KEY

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

## Testing

```bash
pytest
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```
