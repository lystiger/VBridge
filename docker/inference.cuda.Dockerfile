FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
      python3 \
      python3-pip \
      python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/vbridge
ENV PATH=/opt/vbridge/bin:$PATH \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu128 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    HF_HOME=/data/hf

WORKDIR /app
COPY pyproject.toml ./
COPY apps apps
COPY services services
COPY shared shared

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[audio,asr,mt,vad]"

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
