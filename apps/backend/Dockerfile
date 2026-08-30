# DASH Backend — Fly.io Deployment
# Multi-stage build for smaller image
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system deps needed by psycopg, Pillow, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code
COPY . .

# Fly.io sets PORT env var
ENV PORT=8000
ENV DASH_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "dash_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
