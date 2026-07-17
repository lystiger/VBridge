# VBridge Sprint 01 — Platform Foundation

## Implementation Status

Completed on 2026-07-17.

- FastAPI API, shared Pydantic schemas, dependency-injected mock services, and pipeline orchestrator implemented.
- Structured request/stage logging and aggregate JSON latency metrics implemented.
- Browser microphone capture, upload, status, transcript, translation, latency, and WAV playback implemented.
- Docker Compose starts the API and web UI with health-gated dependencies.
- Ruff, 9 Pytest tests with 97.61% coverage, frontend production build, Docker image builds, and live HTTP smoke tests pass.

The Sprint 01 model implementations intentionally remain mocks. Audio streaming is deferred because it is explicitly listed under **NOT INCLUDED**; Sprint 01 uses a completed-response WAV URL.

## Goal

Build the production skeleton of VBridge.

By the end of Sprint 1, the system should support the complete pipeline:

Microphone
    ↓
ASR Service (mock acceptable)
    ↓
Translation Service (mock acceptable)
    ↓
TTS Service (mock acceptable)
    ↓
Web UI

All components must communicate through well-defined APIs.

NO focus on model quality yet.

---

# Success Criteria

By the end of Sprint 1 we should be able to:

- start the backend with one command
- start the frontend with one command
- upload or stream audio
- send audio through the complete pipeline
- receive translated text
- receive streamed audio response
- visualize pipeline status
- collect latency metrics

Model outputs may be mocked.

Pipeline must be real.

---

# Tech Stack

Backend

- FastAPI
- Python 3.12
- Pydantic v2
- Uvicorn

Frontend

- React
- Vite
- Typescript
- Tailwind

Infrastructure

- Docker
- Docker Compose

Testing

- Pytest

---

# Repository Structure

vbridge/

apps/
    api/
    web/

services/
    asr/
    translation/
    tts/

shared/
    schemas/
    config/
    utils/

tests/

docker/

scripts/

docs/

---

# Sprint Deliverables

## 1. FastAPI Backend

Create FastAPI server.

Endpoints

GET /health

GET /metrics

POST /pipeline/process

POST /tts

POST /translation

POST /asr

Use mocked responses initially.

---

## 2. Shared Schemas

Create Pydantic models.

AudioRequest

```python
class AudioRequest(BaseModel):
    session_id: str
    speaker: str
    language: str | None
    audio_path: str
```

ASRResponse

TranslationResponse

TTSResponse

PipelineResponse

Every service MUST use shared schemas.

---

## 3. Pipeline Orchestrator

Implement

PipelineService

Responsibilities

- call ASR
- call Translation
- call TTS
- collect latency
- return final result

No business logic inside API routes.

---

## 4. Service Interfaces

Implement abstract interfaces.

ASRService

TranslationService

TTSService

Current implementation

Mock only.

Example

ASR

returns

"Xin chào"

Translation

returns

"Hello"

TTS

returns

dummy wav

---

## 5. Logging

Every request should generate

request_id

session_id

timestamps

Example

INFO

Pipeline started

↓

ASR completed

↓

Translation completed

↓

TTS completed

↓

Pipeline finished

---

## 6. Metrics

Collect

asr_ms

translation_ms

tts_ms

total_pipeline_ms

Expose

GET /metrics

JSON only.

No Grafana yet.

---

## 7. Frontend

Minimal interface.

Requirements

- Record button

- Stop button

- Transcript

- Translation

- Status

Current Stage

Latency

No fancy UI.

---

## 8. Docker

docker compose up

should start

backend

frontend

No manual setup.

---

## 9. Testing

Unit tests

PipelineService

Schemas

Mock services

Health endpoint

Minimum coverage

70%

---

## 10. CI

GitHub Actions

Run

ruff

pytest

docker build

---

# NOT INCLUDED

Do NOT implement

- Whisper
- NLLB
- TTS
- KD
- GPU inference
- Speaker diarization
- Noise reduction
- Streaming
- Translation quality
- Authentication

These belong to Sprint 2+.

---

# Code Standards

- Type hints everywhere
- No business logic in routes
- Dependency injection
- Async first
- Structured logging
- Pydantic validation
- No hardcoded paths
- Environment variables only

---

# Definition of Done

Sprint 1 is complete when

docker compose up

works

↓

frontend opens

↓

user uploads audio

↓

backend processes request

↓

mock translation returned

↓

mock audio returned

↓

latency displayed

↓

tests pass

↓

CI passes

Nothing else.
