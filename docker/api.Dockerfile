FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY apps apps
COPY services services
COPY shared shared
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
