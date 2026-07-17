# VBridge
Repository of SilentVoix team on VAIC(Vietnam AI Innovation Challenge) 17-19/7/2026
# VBridge

VBridge is a local-first Vietnamese–English meeting translation pipeline. Sprint 01 provides a production-shaped platform skeleton with mocked ASR, translation, and TTS implementations behind shared APIs.

## Run with Docker

Prerequisite: Docker with Compose.

```bash
docker compose up --build
```

Open the web UI at <http://localhost:5173>. The API and interactive documentation are available at <http://localhost:8000> and <http://localhost:8000/docs>.

The UI requests microphone permission, records one turn, uploads it, displays the mock transcript and translation, and plays the generated WAV response.

## Local development

Backend (Python 3.12):

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
uvicorn apps.api.main:app --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## API

- `GET /health`
- `GET /metrics` — average stage and total latency
- `POST /asr`
- `POST /translation`
- `POST /tts`
- `POST /pipeline/process` — JSON contract using a server-visible audio path
- `POST /pipeline/upload` — multipart browser/file upload

All model services are deliberately mocked for Sprint 01. The pipeline orchestration, contracts, uploads, logging, metrics, and generated WAV transport are real.

## Quality checks

```bash
ruff check .
pytest
cd apps/web && npm run build
docker compose build
```

## Sprint 02 inference modes

The default stack remains lightweight and mocked. Local real-model evaluation:

```powershell
pip install -e ".[audio,asr,mt,vad,eval,dev]"
$env:VBRIDGE_ASR_MODE="real"
$env:VBRIDGE_MT_MODE="real"
$env:VBRIDGE_VAD_MODE="silero"
python scripts/eval/run.py --asr-mode real --mt-mode real
```

The selected defaults are `Systran/faster-whisper-base` and `facebook/nllb-200-distilled-600M`. CPU evaluation numbers are wiring evidence only and are not representative of the target RTX 4060.
