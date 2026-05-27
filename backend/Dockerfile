FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./

RUN pip install --upgrade pip && \
    pip install ".[prod]" && \
    python -m patchright install --with-deps chromium

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/backend/artifacts /app/backend/cookie_store /ms-playwright && \
    chown -R appuser:appuser /app /ms-playwright

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
