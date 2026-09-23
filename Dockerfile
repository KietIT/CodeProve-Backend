FROM python:3.11-slim

WORKDIR /app

# Unprivileged account the sandbox runner drops to for user-submitted code, so
# it cannot read the backend process's environment (/proc/<pid>/environ).
RUN useradd --system --no-create-home --shell /usr/sbin/nologin sandbox

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
