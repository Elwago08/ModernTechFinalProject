FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/instance \
    && chown appuser:appuser /app/instance

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser run.py .

USER appuser

ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "exec waitress-serve --listen=0.0.0.0:${PORT:-8080} run:app"]
