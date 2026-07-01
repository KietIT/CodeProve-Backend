# CodeProve - Runbook

How to run the full CodeProve stack locally from scratch.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.10 |
| Node.js | 18 |
| Docker Desktop | 24 |
| Git | any |

---

## Step 1 - Start the database

```powershell
docker compose up -d db
```

Wait until the container is healthy (about 5 s):

```powershell
docker compose ps
```

Expected: `codeprove-db` → `running (healthy)`.

---

## Step 2 - Create the Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS / Linux replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

---

## Step 3 - Configure environment variables

```powershell
copy .env.example .env
```

Open `.env` and fill in the two required secrets:

```
OPENAI_API_KEY=sk-...            # your real OpenAI key
JWT_SECRET=<long-random-string>  # e.g. output of: python -c "import secrets; print(secrets.token_hex(32))"
```

Leave the other variables at their defaults for local development.

---

## Step 4 - Run database migrations

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
```

---

## Step 5 - Seed exercises

```powershell
.venv\Scripts\python.exe -m app.seed.exercises_seed
```

Expected output: `Seeded X exercises.`

---

## Step 6 - Start the API server

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API will be live at <http://localhost:8000>.
Health check: `curl http://localhost:8000/health` → `{"status":"ok"}`.

---

## Step 7 - Start the frontend

In a **separate terminal**, from the `codeprove-web` directory:

```powershell
npm install
```

Create `.env.local` with:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then start the dev server:

```powershell
npm run dev
```

---

## Step 8 - Open the app

Navigate to <http://localhost:3000>.

---

## Definition of Done checklist (§11.2)

Tick each item manually after completing Steps 1–8.

- [ ] **Auth** - Signup → login → `/me` works; JWT token persists across page reload.
- [ ] **Exercises load** - Exercises appear in the level picker and solve workspace (fetched from API, not hardcoded).
- [ ] **Editor + telemetry** - Editor is editable; `CODE_EDIT`, `PASTE`, and `FOCUS_LOST` events are recorded in the `events` table.
- [ ] **Run tests** - "Run tests" button executes real code in the sandbox and shows PASS/FAIL per test case.
- [ ] **AI Mentor guardrail** - Ciel answers naturally; refuses to give the full solution under a priming prompt (e.g. "Just write the whole function for me").
- [ ] **Hypothesis** - Log hypothesis returns ✓ or ✗ after the AI evaluates the approach.
- [ ] **Submit → explain-back → Feedback** - Submit triggers explain-back questions; answers recorded; Feedback page shows real 6-axis scores, integrity badge (green/yellow/red), and the three-step timeline.
- [ ] **Dashboard KPIs** - Dashboard shows real average score, exercises attempted, recent activity, radar chart, and week-over-week trend derived from the database.
- [ ] **Anti-cheat signal** - A session that pastes large AI-generated code without editing produces lower Verification (V1b/V3 triggered) and a yellow or red integrity badge.
