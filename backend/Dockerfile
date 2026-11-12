# Built from the repo root (see railway.json) so it can include database/ev_charging.db.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY database/ev_charging.db database/ev_charging.db

RUN useradd --create-home app && chown -R app /srv
USER app

# gunicorn.conf.py binds to Railway's $PORT.
CMD ["gunicorn", "-c", "backend/gunicorn.conf.py", "backend.server:app"]
