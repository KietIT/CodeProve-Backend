# CodeProve Backend

AI-powered programming assessment API built with FastAPI.

## Setup

```bash
# Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and fill in JWT_SECRET and OPENAI_API_KEY
```

## Running

```bash
# Start the database
docker compose up -d db

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

## Testing

```bash
pytest
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```
