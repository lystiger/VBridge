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

## Android conversation protocol

The conversation API adds `POST /sessions`, `POST /sessions/{session_id}/participants`, and
`WS /sessions/{session_id}/ws?participant_id=...` without changing the existing REST API.

Create a conversation, then join each phone with opposite language directions:

```http
POST /sessions
```

```json
{"session_id":"4a8a..."}
```

```http
POST /sessions/4a8a.../participants
Content-Type: application/json

{"source_language":"vi","target_language":"en"}
```

Keep the returned `participant_id` on the phone. To reconnect, repeat the join request with
that `participant_id`, then open:

```text
ws://192.168.1.10:8000/sessions/4a8a.../ws?participant_id=9b2c...
```

For each complete recorded turn, send one text frame followed immediately by one binary frame.
The binary frame contains the same complete encoded audio file that `/pipeline/upload` accepts.

```json
{"type":"turn.start","sequence":1,"source_language":"vi","target_language":"en"}
```

The server acknowledges the turn and broadcasts ordered results to both connected phones:

```json
{"type":"turn.accepted","session_id":"4a8a...","participant_id":"9b2c...","sequence":1,"status":"queued"}
{"type":"transcript.final","session_id":"4a8a...","participant_id":"9b2c...","sequence":1,"source_language":"vi","target_language":"en","text":"Xin chao"}
{"type":"translation.final","session_id":"4a8a...","participant_id":"9b2c...","sequence":1,"source_language":"vi","target_language":"en","text":"Hello","audio_url":"/audio/4a8a....wav","asr_ms":12.4,"mt_ms":4.2}
{"type":"turn.completed","session_id":"4a8a...","participant_id":"9b2c...","sequence":1,"queue_ms":0.3,"dispatch_ms":0.4,"end_to_end_ms":20.1}
```

Sequence numbers start at 1 per participant. Out-of-order turns wait for missing earlier turns.
Retries with a completed sequence replay cached final events with `"duplicate": true`; retries do
not run inference twice. Session and retry state are process-local, expire on server restart, and
require a single API worker until shared storage is introduced.
