FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard] aio-pika sqlalchemy[asyncio] asyncpg alembic httpx prometheus-client python-json-logger

COPY app ./app
COPY migrations ./migrations

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${SERVER_B_PORT:-9000}"]
