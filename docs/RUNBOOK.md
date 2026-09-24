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

Compose reads the DB password from `.env`, so create it first (see Step 3 for
the other values) and set `POSTGRES_PASSWORD` to a long random string - and the
same password in `DATABASE_URL`:

```powershell
copy .env.example .env
docker compose up -d db
```

Postgres is published on `127.0.0.1:5432` only (loopback), never on the network.

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

Open `.env` (created in Step 1) and fill in the two required secrets:

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

---

# Production (EC2)

Commands below run on the EC2 host (Ubuntu) from the repo directory unless
noted. Replace `<bucket>` / `<region>` with your values.

## Network exposure

Both published ports are bound to loopback in `docker-compose.yml`:

| Service | Host binding | Public entry point |
|---|---|---|
| backend | `127.0.0.1:8000` | Cloudflare tunnel (`http://backend:8000` over the compose network) |
| db | `127.0.0.1:5432` | none |

Docker-published ports bypass ufw/iptables, so the loopback binding is what
keeps them private. The EC2 Security Group should allow inbound SSH (22, ideally
from your IP only) and nothing else. Check after deploying:

```bash
sudo ss -ltnp | grep -E ':(8000|5432) '   # both must show 127.0.0.1, never 0.0.0.0
curl -fsS http://127.0.0.1:8000/health    # {"status":"ok"}
```

## Rotating the database password

`POSTGRES_PASSWORD` is only applied when the data volume is first created, so
editing `.env` alone does NOT change the password of an existing database.
Change it inside Postgres first, then make `.env` match:

```bash
NEW_PG_PW=$(openssl rand -hex 32)   # hex: safe in DATABASE_URL without encoding
printf "ALTER USER codeprove WITH PASSWORD '%s';\n" "$NEW_PG_PW" \
  | docker exec -i codeprove_db psql -U codeprove -d codeprove -v ON_ERROR_STOP=1
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PG_PW|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://codeprove:$NEW_PG_PW@localhost:5432/codeprove|" .env
unset NEW_PG_PW
docker compose up -d
```

## Database backups (S3)

`scripts/backup_db.sh` dumps the database (`pg_dump -Fc`, run inside the db
container), checks the archive is readable, uploads it to S3 with server-side
encryption and a sha256 in the object metadata, then reads the object back to
confirm the size. It exits non-zero on any failure.

Retention lives in an S3 lifecycle rule, not in the script, so the EC2 role
never gets delete rights: a compromised server cannot wipe the backups.

### 1. Create the bucket (one-time, from an admin machine)

```bash
aws s3api create-bucket --bucket <bucket> --region <region> \
  --create-bucket-configuration LocationConstraint=<region>
aws s3api put-public-access-block --bucket <bucket> --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket <bucket> --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration --bucket <bucket> --lifecycle-configuration '{
  "Rules": [{
    "ID": "expire-db-backups",
    "Status": "Enabled",
    "Filter": {"Prefix": "postgres/"},
    "Expiration": {"Days": 30},
    "NoncurrentVersionExpiration": {"NoncurrentDays": 7},
    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}
  }]
}'
```

Versioning means an overwritten object keeps its previous version, which the
EC2 role (no `s3:DeleteObjectVersion`) cannot remove.

### 2. Give the EC2 instance an IAM role (no access keys on the server)

IAM → Roles → Create role → trusted entity "AWS service / EC2" → add this inline
policy (least privilege: write/read backups under the prefix, list the prefix,
no delete). Then EC2 → the instance → Actions → Security → Modify IAM role. If
the instance already has a role, add the policy to that role instead.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadWriteBackups",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::<bucket>/postgres/*"
    },
    {
      "Sid": "ListBackups",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<bucket>",
      "Condition": {"StringLike": {"s3:prefix": ["postgres/*"]}}
    }
  ]
}
```

### 3. Install the AWS CLI and configure `.env` (on EC2)

```bash
sudo snap install aws-cli --classic
aws sts get-caller-identity          # must show the instance role (assumed-role/...)
```

Add to `.env` (see `.env.example`):

```
BACKUP_S3_BUCKET=<bucket>
BACKUP_S3_PREFIX=postgres
BACKUP_AWS_REGION=<region>
BACKUP_HEALTHCHECK_URL=              # optional, e.g. https://hc-ping.com/<uuid>
```

### 4. First run + restore test

A backup is only trusted once it has been restored. `verify` restores into a
scratch database, prints row counts next to the live ones, and drops it - it
never touches the live database.

```bash
scripts/backup_db.sh
scripts/restore_db.sh list
scripts/restore_db.sh verify latest
```

Repeat `verify latest` monthly.

### 5. Schedule it (cron)

`crontab -e` and add (19:00 UTC = 02:00 Vietnam time). cron's default PATH lacks
`/snap/bin`, where the snap AWS CLI lives, so set it explicitly:

```
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
0 19 * * * /home/ubuntu/CodeProve-Backend/scripts/backup_db.sh >> /home/ubuntu/codeprove-backup.log 2>&1
```

The user running cron must be able to use Docker (member of the `docker`
group). Check `/home/ubuntu/codeprove-backup.log` the next day for
`backup OK`. For alerting, set `BACKUP_HEALTHCHECK_URL` to a healthchecks.io
check with a 1-day period: it alerts both on an explicit failure ping and when
no success ping arrives at all (e.g. cron or the server is down).

## Restoring the database

```bash
scripts/restore_db.sh restore <key-from-list>
```

It asks you to type the database name, writes a safety dump of the current
database to `$HOME`, stops the backend, recreates the database from the backup,
and starts the backend again. If the restore fails, the backend is deliberately
left stopped (starting it would let alembic create an empty schema) and the
script prints the rollback command:

```bash
scripts/restore_db.sh restore ~/codeprove_pre_restore_<timestamp>.dump
```
