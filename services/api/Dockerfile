FROM python:3.11-slim

WORKDIR /app/services/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/pyproject.toml services/api/README.md ./
COPY services/api/app ./app
COPY services/api/alembic ./alembic
COPY services/api/alembic.ini ./
COPY services/api/scripts ./scripts
COPY fixtures /app/fixtures

RUN pip install --no-cache-dir .

COPY services/api/scripts/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV FIXTURES_ROOT=/app/fixtures \
    STORAGE_ROOT=/app/storage \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
