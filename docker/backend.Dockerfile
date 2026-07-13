# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/backend/pyproject.toml apps/backend/README.md ./apps/backend/
COPY apps/backend/dash_backend ./apps/backend/dash_backend/

RUN pip install --upgrade pip && \
    pip install ./apps/backend

FROM base AS runtime

RUN groupadd --gid 1000 dash && \
    useradd --uid 1000 --gid dash --shell /bin/bash --create-home dash

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY apps/backend/dash_backend ./dash_backend

USER dash

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "dash_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
