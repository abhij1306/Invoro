FROM ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv

FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/backend/.venv/bin:$PATH

WORKDIR /app/backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates python3 && \
    ln -s /usr/bin/python3 /usr/local/bin/python && \
    rm -rf /var/lib/apt/lists/*

COPY backend/ ./

# Install exactly the frozen application lock. uv is a pinned build-only mount.
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    uv sync --frozen --no-dev && \
    python -m patchright install --with-deps chromium && \
    apt-get purge -y xvfb xserver-common && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /root/.cache/uv && \
    rm -rf /var/lib/apt/lists/*

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
