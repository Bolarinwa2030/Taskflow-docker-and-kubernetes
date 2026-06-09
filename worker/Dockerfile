# ── Stage 1: build deps ────────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user
RUN groupadd -r worker && useradd -r -g worker worker

WORKDIR /app

# Copy installed packages from build stage
COPY --from=deps /install /usr/local
COPY worker.py .

USER worker

# Workers don't expose a port — they pull from Redis
CMD ["python", "-u", "worker.py"]
