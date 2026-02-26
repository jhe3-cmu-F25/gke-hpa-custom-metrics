# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Install Python dependencies into a clean layer so the final image stays small.
FROM python:3.11-slim AS builder

WORKDIR /app

# Install deps first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Flask listens on this port (override via docker-compose or env var)
EXPOSE 5000

# Run with the built-in dev server.
# For production swap this for: gunicorn -w 4 -b 0.0.0.0:5000 app:app
CMD ["python", "app.py"]
