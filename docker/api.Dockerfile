FROM python:3.12-slim

# System libraries for audio decoding used by the real inference stack
# (faster-whisper/PyAV for uploads, soundfile/librosa for the streaming path).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pull CPU-only torch wheels: smaller image, no CUDA runtime dragged in.
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
# Model weights download lazily on first inference; cache them on a mounted volume
# (see docker-compose) so restarts do not re-download ~2.5 GB.
ENV HF_HOME=/data/hf

COPY pyproject.toml ./
COPY apps apps
COPY services services
COPY shared shared

# Empty by default (mock stack). docker-compose passes [audio,asr,mt,vad] for real models.
ARG VBRIDGE_EXTRAS=""
RUN pip install --no-cache-dir ".${VBRIDGE_EXTRAS}"

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
