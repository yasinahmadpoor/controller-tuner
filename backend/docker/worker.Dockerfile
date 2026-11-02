FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GA_ENGINE_REPO=/app/engines/gaTunerPID \
    MANUAL_ENGINE_REPO=/app/engines/tunerPID \
    ARTIFACT_DIR=/data/artifacts

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app
COPY gaTunerPID /app/engines/gaTunerPID
COPY tunerPID /app/engines/tunerPID

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/artifacts \
    && chown -R app:app /app /data

USER app

CMD ["celery", "-A", "app.workers.celery_app:celery_app", "worker", "-Q", "ga,maintenance", "--loglevel=INFO"]
