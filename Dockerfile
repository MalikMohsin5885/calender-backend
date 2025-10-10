# Multi-stage Dockerfile (venv based) for Django deployment on GCP Cloud Run / GKE
# - uses a virtualenv to avoid --user and pip-as-root warnings
# - exposes a root-level /health/ endpoint via the Django app
# - uses a stdlib-based HEALTHCHECK to avoid relying on third-party packages during probe

# Stage 1: Base image with system deps
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    default-libmysqlclient-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stage 2: Install Python dependencies into a virtualenv
FROM base AS builder

# Create a virtualenv and install deps into it
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Stage 3: Final image
FROM base AS final

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create less-privileged user
RUN groupadd -r django && useradd -r -g django -m -d /home/django django
WORKDIR /app

# Copy application code
COPY --chown=django:django . .

# Ensure folders exist and fix ownership
RUN mkdir -p /app/staticfiles /app/media && chown -R django:django /app/staticfiles /app/media /home/django

# Collect static files (do not fail build if collectstatic needs DB: allow it to run but ignore failures)
USER django
ENV DJANGO_SETTINGS_MODULE=backend.settings
RUN python manage.py collectstatic --noinput || true

# Switch to non-root for runtime
USER django

EXPOSE 8080

# Healthcheck uses stdlib urllib to avoid third-party import issues
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD /bin/sh -c 'python - <<PY\nimport urllib.request, sys\ntry:\n    urllib.request.urlopen("http://127.0.0.1:8080/health/", timeout=2)\n    sys.exit(0)\nexcept Exception:\n    sys.exit(1)\nPY'

# Start the app
CMD exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2} \
    --worker-class gthread \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${GUNICORN_LOG_LEVEL:-info}
