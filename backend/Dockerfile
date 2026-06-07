# Tsumiki backend — FastAPI + LangGraph agent service.
# Python 3.11 (slim) has prebuilt wheels for chromadb/chroma-hnswlib, avoiding a
# from-source compile. build-essential is kept as a safety net for any sdist.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (only needed if a dependency lacks a wheel; cheap to include).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code (.dockerignore keeps .venv, .chroma, tests, .env.local out).
COPY . .

# Cloud Run provides $PORT (defaults to 8080). Bind 0.0.0.0 so it is reachable.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
