# FastAPI recommender. Build context: repo root (it needs static/processed/).
# Railway: Root Directory = "/" and variable RAILWAY_DOCKERFILE_PATH=deploy/fastapi.Dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# logic.py finds the station snapshot at ../../static/processed relative to
# itself, so keep the repo layout: /app/AI/Algorithm and /app/static/processed.
WORKDIR /app/AI/Algorithm
COPY AI/Algorithm/requirements.txt ./
RUN pip install -r requirements.txt
COPY AI/Algorithm/ ./
COPY static/processed/ /app/static/processed/

# "::" listens on IPv6 and IPv4, which Railway's private network needs.
CMD uvicorn app:app --host :: --port ${PORT:-8000}
