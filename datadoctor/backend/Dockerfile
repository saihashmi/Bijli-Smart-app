# syntax=docker/dockerfile:1
# DataDoctor AI API. Build from the datadoctor/ folder:  docker build -f backend/Dockerfile .
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/backend

COPY backend/requirements.txt .
# Behind a TLS-inspecting proxy, pass its CA as a build secret:  --secret id=ca,src=/path/to/ca.crt
RUN --mount=type=secret,id=ca,required=false \
    if [ -s /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install -r requirements.txt

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini .
COPY sample-data /srv/sample-data

# Never run as root. Only the storage volume is writable.
RUN useradd --system --uid 10001 --home-dir /srv --shell /usr/sbin/nologin datadoctor \
    && mkdir -p /data && chown datadoctor:datadoctor /data
USER datadoctor
ENV STORAGE_DIR=/data SAMPLES_DIR=/srv/sample-data
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
# One process: rate limits, locks and caches are in memory (see README, Known limits).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
