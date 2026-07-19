FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU inference image. A longer timeout makes the large PyTorch wheel resilient
# to slow challenge/demo networks; BuildKit retains completed layers on retry.
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    HF_HOME=/data/hf

COPY pyproject.toml ./
COPY apps apps
COPY services services
COPY shared shared

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[audio,asr,mt,vad]"

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
