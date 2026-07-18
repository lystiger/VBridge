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

## Two-phone room protocol

Rooms are process-local and support exactly two participants. Run one API worker; room state is
lost when the server restarts. Existing inference and `/pipeline/stream` endpoints are unchanged.

Phone A creates a room:

```http
POST /rooms
Content-Type: application/json

{"display_name":"Phone A","source_language":"vi","target_language":"en"}
```

The `201` response contains `room_id`, a six-character `room_code`, the creator participant,
`access_token`, status, and expiration. Phone B joins with the code:

```http
POST /rooms/join
Content-Type: application/json

{"room_code":"7KQ4MP","display_name":"Phone B","source_language":"en","target_language":"vi"}
```

Each phone connects with its own returned token:

```text
ws://192.168.1.10:8000/ws/rooms/{room_id}?token={access_token}
```

All JSON messages use the canonical envelope. Start a 16 kHz, mono, signed 16-bit PCM turn:

```json
{
  "type":"audio.start",
  "event_id":"4fe8c25f-b159-4ec9-ae9a-95c4db61e58d",
  "room_id":"8b1b6c55-7e5b-4cd1-b30a-2a91eac905f4",
  "participant_id":"a88ac568-eafb-452f-8c43-4a988420797b",
  "sequence":1,
  "timestamp":"2026-07-18T16:45:01Z",
  "payload":{"audio_format":"pcm_s16le","sample_rate_hz":16000,"channels":1,"source_language":"vi","target_language":"en"}
}
```

Send one or more binary PCM frames, followed by `audio.end` with a new event ID and a higher
sequence. The server runs the accumulated turn once through the existing streaming pipeline and
broadcasts one identical authoritative result to both phones:

```json
{
  "type":"translation.result",
  "event_id":"4fe8c25f-b159-4ec9-ae9a-95c4db61e58d",
  "room_id":"8b1b6c55-7e5b-4cd1-b30a-2a91eac905f4",
  "participant_id":"a88ac568-eafb-452f-8c43-4a988420797b",
  "sequence":1,
  "timestamp":"2026-07-18T16:45:04Z",
  "payload":{"speaker_id":"a88ac568-eafb-452f-8c43-4a988420797b","source_language":"vi","target_language":"en","source_text":"Xin chao","translated_text":"Hello","inference_mode":"server"}
}
```

Reconnect using the same token; the newest socket replaces a stale connection. `ping` produces
`pong`. Duplicate event IDs return `DUPLICATE_EVENT`; repeated/lower sequences return
`OUT_OF_ORDER_EVENT`; sequence gaps are accepted and logged. Errors use the same envelope with
`payload.code`, `payload.message`, and `payload.retryable`.

Room recovery and closure use authenticated REST calls:

```http
GET /rooms/{room_id}
Authorization: Bearer {access_token}

DELETE /rooms/{room_id}
Authorization: Bearer {access_token}
```

Audio turns are limited to 30 seconds and 10 MB by default. Set a private
`VBRIDGE_ROOM_TOKEN_SECRET` in deployments; tokens are HMAC-signed, room/participant-bound, and
expire with the room TTL.
