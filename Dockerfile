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

EXPOSE 5000

CMD ["sh", "-c", "python -m flask --app run.py init-db && exec waitress-serve --listen=0.0.0.0:5000 run:app"]
