# =============================================================================
# VERITY Backend — Multi-stage Dockerfile
# =============================================================================

# --- Base stage ---------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install uv

# --- Dependencies stage -------------------------------------------------------
FROM base AS deps

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

# --- Development stage --------------------------------------------------------
FROM deps AS development

# Dev tools already installed above
COPY . .

EXPOSE 8000

# --- Production stage ---------------------------------------------------------
FROM base AS production

# Only install production deps
COPY pyproject.toml .
RUN uv pip install --system -e "." --no-dev

COPY . .

# Non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
