# syntax=docker/dockerfile:1
# ArcHub platform — single-stage image running the standalone FastAPI app.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    ARCHUB_CMS_DB=/data/archub_cms.db \
    ARCHUB_RUNTIME_EXPORT_DIR=/data/archub_runtime \
    ARCHUB_PLUGIN_DIRS=/app/plugins

WORKDIR /app

# Install dependencies first for better layer caching. The PostgreSQL extra is
# included so the ITSM plugin can use Postgres storage when ARCHUB_ITSM_PG_DSN is set.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY plugins ./plugins
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[server,postgres]" \
    && mkdir -p /data \
    && useradd --create-home --uid 10001 archub \
    && chown -R archub:archub /data /app

# Run as a non-root user with a writable data volume.
USER archub

VOLUME ["/data"]
EXPOSE 8000

# A lightweight healthcheck against the API docs endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/docs').status==200 else 1)"

CMD ["uvicorn", "archub_cms.app:create_archub_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
