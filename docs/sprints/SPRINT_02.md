# Sprint 02 — coding agent implementation brief

You are implementing Sprint 02 of VBridge (SilentVoix / VAIC 2026). Work head-down and in order. A human is researching and downloading the final models in parallel — **do not wait for them and do not hardcode any final model choice.** Your job is to make the wiring real and correct on tiny/stub models so the chosen checkpoint drops in later as a one-line config change.

## Golden rule — the contract is the seam

Sprint 01 delivered a working skeleton: real pipeline orchestration, request/response contracts, upload transport, `/metrics` latency, and WAV playback, with **mocked** ASR/MT/TTS services behind stable APIs (`/asr`, `/translation`, `/tts`, `/pipeline/process`, `/pipeline/upload`).

- **Do NOT modify the orchestration layer or the API contracts.** Implement real services that satisfy the *existing* request/response shapes.
- If a real model can only fit by changing a contract, STOP and leave a `# BLOCKED:` comment explaining why. Do not redesign around it.
- Before writing anything, read the existing service and contract code to learn the exact shapes and module layout. Match them.

## Hard constraints (never violate)

- **No cloud / hosted inference** anywhere in the translation path. On-device only.
- **No training or fine-tuning.** You load pre-existing models only.
- **No ROCm.** Backends are CPU and CUDA only.
- **Do not commit model weights, secrets, `.env`, or audio/transcript data.** Weights load from a configured path/cache; add paths to `.gitignore` if needed.
- Keep `docker compose up --build`, `ruff check .`, and `pytest` green at every checkpoint.

## Configuration you must add first (Task 0)

Introduce two independent switches, read from env with safe defaults, threaded through the services:

- `INFERENCE_BACKEND` = `cpu` (default) | `cuda`
- Per-stage model selection, e.g. `ASR_MODEL`, `MT_MODEL`, `TTS_VOICE`, plus a per-stage mode `ASR_MODE` / `MT_MODE` / `TTS_MODE` = `mock` | `real`.

Semantics:
- `mock` keeps the Sprint 01 mock for that stage (so the pipeline still runs if a real model isn't downloaded yet).
- `real` loads the configured model on the configured backend.
- Default the repo to **`*_MODE=mock` except where you've validated a real tiny model**, so a fresh clone always boots.

This is what lets you build now and lets the human swap in the real checkpoint later without touching code — only env values change.

## Task order (do sequentially, verify each before moving on)

### T0 — Config plumbing
Add the env switches above and wire them into service construction. Add them to `.env.example` with comments. 
*Verify:* app boots with all stages `mock`; `INFERENCE_BACKEND=cpu` is the default; no stage hardcodes a checkpoint.

### T1 — Deployment: dual backend, CUDA no longer mandatory
Rewrite `docker/` and `docker-compose.yml` so the image is **CPU by default** and CUDA is opt-in via `INFERENCE_BACKEND=cuda`. Remove any hard requirement on `nvidia/cuda`, `device: cuda`, or `NVIDIA_VISIBLE_DEVICES` from the default path; gate GPU config behind the backend flag. Pin CPU-capable wheels (CTranslate2 CPU/oneDNN works on both AMD and Intel; CUDA wheels used only when backend=cuda).
*Verify:* `docker compose up --build` comes up on a machine with **no CUDA present**, all stages `mock` or tiny.

### T2 — Real ASR service (validate on tiny)
Implement the real ASR service behind the existing `/asr` contract using faster-whisper (CTranslate2). Model and compute type come from config (`ASR_MODEL`, `INFERENCE_BACKEND`, INT8 on CPU / FP16 on CUDA). Default `ASR_MODEL` to a **tiny** checkpoint for wiring validation. Language routing by translation direction (VN vs EN).
*Verify:* with `ASR_MODE=real` and a tiny model, `POST /asr` returns a real transcript for a VN clip and an EN clip. Transcript quality does not matter yet — the contract round-trip and real inference path do.

### T3 — Real MT service (validate on tiny/available)
Implement the real MT service behind `/translation`. Target NLLB-200-distilled-600M with `vie_Latn ↔ eng_Latn`, model + backend from config. If the NLLB weights aren't downloaded yet, keep `MT_MODE=mock` as the committed default and make sure `MT_MODE=real` works the moment the weights are present — do not block T4+ on the download.
*Verify:* with `MT_MODE=real` and a present model, `/translation` returns correct-direction output both ways. If weights absent, mock still serves and the pipeline runs.

### T4 — VAD endpointing (turn-taking)
Add Silero VAD (ONNX, CPU) to auto-detect end-of-turn so a normal utterance triggers the pipeline without a manual stop. Single speaker only; no overlap handling.
*Verify:* an uploaded clip with a trailing pause is segmented and fires the pipeline automatically.

### T5 — Glossary hook at MT
Add a mechanism at the MT stage to load a business glossary (term dictionary file — the data owner will supply `glossary.*`; commit a small placeholder with 3–5 example terms) and enforce consistent translation of those terms. Keep it swappable/config-driven.
*Verify:* the placeholder terms translate identically across repeated turns; absent glossary file degrades gracefully (no crash).

### T6 — Streaming partials to the UI
Emit partial transcript/translation to `apps/web` as they become available, reducing perceived latency. Keep the existing final-WAV transport unchanged.
*Verify:* the UI shows text updating before the audio finishes; final WAV still plays.

### T7 — Real latency instrumentation
Extend `/metrics` to log **real** per-stage latency and RTF per utterance, tagged with backend and model. Remove reliance on mock timings.
*Verify:* `/metrics` reports real stage timings when stages are `real`. Leave a clear `# NOTE: tiny-model timings are not representative` marker — see the warning below.

### T8 — Eval harness
Add `scripts/eval` that runs the test dialogues (data owner supplies fixtures in `tests/`; commit a tiny placeholder set) through the pipeline and prints a table: meaning/accuracy score (BLEU or COMET-lite if available, else placeholder) + per-stage RTF + total latency. Parameterize by backend/model so the same command benchmarks tiny-now and real-later.
*Verify:* one command produces the table on the placeholder fixtures.

## Critical warning you must respect

**Tiny-model latency numbers are throwaway.** They prove the workflow is correct; they say nothing about whether the real model on the real GPU hits the sub-2s budget. Do not populate any "budget met" claim from tiny-model runs. Leave the real latency assessment for when the chosen model runs on the target card (RTX 4060, `INFERENCE_BACKEND=cuda`). Mark tiny/CPU eval output explicitly as non-representative.

## Definition of done for the sprint

1. Config switches (`INFERENCE_BACKEND`, per-stage model/mode) work; fresh clone boots on defaults with no CUDA.
2. ASR and MT real services satisfy the existing contracts and run bidirectionally on a tiny/available model.
3. VAD endpointing, glossary hook, and streaming partials are implemented and pass their verifies.
4. `/metrics` reports real timings; eval harness runs on placeholder fixtures.
5. Swapping to the final model = changing env values only (`ASR_MODEL`, `MT_MODEL`, `*_MODE=real`, `INFERENCE_BACKEND=cuda`) — no code change required.
6. `ruff`, `pytest`, `docker compose build`, and `apps/web` build all green.

## Out of scope — refuse on sight

Cloud inference · training/fine-tuning · ROCm · overlap/multi-speaker diarization · extra language pairs · UI redesign beyond dual-view + streaming text · committing model weights.

## What to leave for the human (do not attempt)

- Choosing the final ASR/MT checkpoints and downloading weights.
- The real accuracy/latency benchmark on the RTX 4060.
- The production glossary content and the full test-dialogue set (you commit small placeholders only).
