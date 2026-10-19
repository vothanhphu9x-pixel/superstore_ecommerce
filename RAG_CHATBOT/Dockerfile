FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    APP_LOG_DIR=/var/log/superstore

WORKDIR /app

COPY requirements.txt requirements-production.txt ./

RUN pip install --no-cache-dir -r requirements-production.txt

COPY analytics ./analytics
COPY api ./api
COPY core ./core
COPY scripts ./scripts

RUN useradd --uid 10001 --user-group --create-home appuser \
    && mkdir -p /app/data /app/logs /var/log/superstore \
    && chown -R appuser:appuser /app/data /app/logs /var/log/superstore

USER 10001:10001

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live', timeout=3)"

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
