FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/backend/.venv/bin:$PATH

WORKDIR /app/backend

# skipcq: DOK-DL3008 - base-image package versions must track Debian security updates.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./

# Install exactly the frozen application lock. uv itself is pinned as build tooling.
# hadolint ignore=DL3013
RUN python -m pip install --no-cache-dir uv==0.11.28 && \
    uv sync --frozen --no-dev && \
    python -m patchright install --with-deps chromium

RUN groupadd --gid 10001 appuser && \
    useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash appuser && \
    mkdir -p /app/backend/artifacts /app/backend/cookie_store /ms-playwright && \
    chown -R appuser:appuser \
      /app/backend/artifacts \
      /app/backend/cookie_store \
      /home/appuser

USER appuser

EXPOSE 9000

ENTRYPOINT ["python", "docker_entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
