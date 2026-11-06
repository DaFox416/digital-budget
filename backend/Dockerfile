FROM python:3.12-slim

# Don't write .pyc files and flush logs immediately (so `docker compose logs` shows them live)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy only what's needed to install dependencies first, so Docker caches this layer
# and only reinstalls when pyproject.toml changes.
COPY pyproject.toml ./
COPY app ./app
RUN pip install -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
