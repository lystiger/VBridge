FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY apps apps
COPY services services
COPY shared shared

# Lightweight room, relay, database, and mock-pipeline image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "."

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
