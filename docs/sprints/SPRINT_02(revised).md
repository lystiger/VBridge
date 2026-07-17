Sprint 02 — coding agent implementation brief (rev. 2)

## Implementation status — completed 2026-07-17

- CPU/mock defaults and optional `audio`, `asr`, `mt`, `vad`, and `eval` dependency groups implemented.
- `Systran/faster-whisper-base` real ASR and bidirectional NLLB real MT validated locally on confirmed fixtures; inference runs off the event loop.
- Config-driven glossary, independent WebSocket streaming orchestrator, Silero ONNX endpointing, replaceable partial events, and final WAV playback implemented.
- Metrics retain original fields and add bounded utterance history, backend/model/mode tags, audio duration, and ASR RTF.
- Eval harness reports fixture WER, BLEU, RTF, and total latency with an explicit non-representative CPU/tiny/base warning.
- Ruff, 16 Pytest tests, frontend build, Docker builds, and live mock-default Compose smoke checks pass.

The lightweight Compose default uses mock models and energy endpointing. Set `VBRIDGE_EXTRAS=[vad,asr,mt]` and `VBRIDGE_VAD_MODE=silero` for an inference image; model weights remain external and are never committed.

You are implementing Sprint 02 of VBridge (SilentVoix / VAIC 2026). Work head-down and in order. A human is researching and downloading the final models and recording test audio in parallel — do not wait for them and do not hardcode any final model choice. Your job is to make the wiring real and correct on tiny/stub models so the chosen checkpoint drops in later as a late config change.


Rev. 2 incorporates review feedback: the golden rule now permits backward-compatible additions, streaming is a separate orchestrator, VAD is coupled to a streaming transport, real TTS is deferred, real inference must not block the event loop, dependencies are split into optional groups, and audio fixtures are defined.



Golden rule — the contract is the seam (amended)

Sprint 01 delivered a working skeleton: real pipeline orchestration (services/pipeline.py, PipelineService.process()), request/response contracts (shared/schemas/models.py), upload transport, /metrics latency, and WAV playback, with mocked ASR/MT/TTS services behind stable APIs.


Do not remove or incompatibly change existing endpoints, request fields, or response fields. Backward-compatible additive fields and new streaming/upload endpoints are permitted.
Preserve PipelineService.process() unchanged for the existing synchronous pipeline. Introduce a separate StreamingPipelineService (+ new WebSocket/SSE endpoint) for streaming behavior — do not bolt streaming onto the sequential orchestrator, and do not move orchestration logic into API routes (Sprint 01's "no business logic in routes" standard holds).
If a real model can only fit by breaking a contract, STOP and leave a # BLOCKED: comment. Additive extension is fine; incompatible change is not.
Before writing anything, read the existing service, contract, and route code to learn the exact shapes and module layout. Match them.


Hard constraints (never violate)


No cloud / hosted inference in the translation path. On-device only.
No training or fine-tuning. Load pre-existing models only.
No ROCm. Backends are CPU and CUDA only.
Real inference must not block the event loop. faster-whisper / CTranslate2 / Transformers inference is synchronous. Run it in a worker thread or dedicated executor (asyncio.to_thread or a pool) behind the existing async service interfaces. Never call blocking inference directly from async def.
Do not commit model weights, secrets, .env, or sensitive audio/transcript data. Weights load from a configured path/cache; add paths to .gitignore if needed. (Scripted, non-sensitive test clips are the one committed-audio exception — see Fixtures.)
Keep docker compose up --build, ruff check ., and pytest green at every checkpoint.


Configuration you must add first (T0)

Two independent switches, read from env with safe defaults, threaded through service factories:


INFERENCE_BACKEND = cpu (default) | cuda
Per-stage model selection + mode: ASR_MODEL / MT_MODEL / TTS_VOICE, and ASR_MODE / MT_MODE / TTS_MODE = mock | real.


Semantics:


mock keeps the Sprint 01 mock (so the pipeline runs even if a real model isn't downloaded yet).
real loads the configured model on the configured backend, via the executor offload above.
Default the repo to *_MODE=mock everywhere except where you've validated a real tiny model, so a fresh clone always boots with zero model downloads.
TTS_MODE=real must fail fast with a clear configuration error — real TTS is deferred this sprint (see T-note on TTS). TTS_VOICE is accepted and stored but unused until a later sprint.


This is what lets you build now and lets the human swap in the real checkpoint later by changing env values only — no code change.

Dependency strategy (part of T0/T1)

Split optional extras into groups so a mock-only clone stays small: base, asr, mt, vad, eval. Fresh-clone mock startup must not require any inference package download or model weights. Decide via build targets or extras whether the production image installs all inference groups; document the choice in the compose/docker files.

Task order (do sequentially, verify each before moving on)

T0 — Config plumbing + service factories

Add the env switches and dependency groups above; wire into service construction via factories. Add everything to .env.example with comments.
Verify: app boots with all stages mock, INFERENCE_BACKEND=cpu default, no hardcoded checkpoint, no inference packages needed to start. TTS_MODE=real raises a clear config error.

T1 — Deployment: CPU default, CUDA opt-in, optional inference deps

Rewrite docker/ and docker-compose.yml so the image is CPU by default and CUDA is opt-in via INFERENCE_BACKEND=cuda. Remove any hard requirement on nvidia/cuda, device: cuda, or NVIDIA_VISIBLE_DEVICES from the default path; gate GPU config behind the flag. Wire the optional dependency groups.
Verify: docker compose up --build comes up on a machine with no CUDA present, all stages mock, pulling no model weights.

T2 — Real ASR service (validate on tiny + fixtures)

Implement the real ASR service behind the existing /asr contract using faster-whisper (CTranslate2), model + compute type from config (INT8 on CPU, FP16 on CUDA), inference offloaded to a worker thread. Default ASR_MODEL to a tiny checkpoint for wiring validation. Language routing by direction. Because /asr takes a server-visible audio_path, T2 verification uses the mounted committed fixtures at tests/fixtures/audio/ (see Fixtures). You may add an additive /asr/upload (multipart) endpoint if convenient — it must not change /asr.
Verify: with ASR_MODE=real + tiny model, POST /asr returns a real transcript for vi_clean_01.wav and en_clean_01.wav. Transcript quality does not matter yet — the real inference path and contract round-trip do. If fixtures are absent, leave # BLOCKED: awaiting tests/fixtures/audio/ and continue to T3.

T3 — Real MT service (validate on tiny/available)

Implement the real MT service behind /translation (NLLB-200-distilled-600M, vie_Latn ↔ eng_Latn, model + backend from config, executor-offloaded). If NLLB weights aren't downloaded, keep MT_MODE=mock as committed default and ensure MT_MODE=real works the moment weights are present. Do not block later tasks on the download.
Verify: with MT_MODE=real + present model, /translation returns correct-direction output both ways; absent weights → mock serves, pipeline runs.

T4 — Glossary hook at MT

Add a config-driven mechanism at the MT stage to load a business glossary (term dictionary) and enforce consistent translation of those terms. The data owner supplies the real file; commit a small placeholder with 3–5 terms.
Verify: placeholder terms translate identically across repeated turns; absent glossary degrades gracefully (no crash).

T5 — Streaming audio transport (new orchestrator)

Add a streaming transport: chunked/continuous browser audio to the backend over a new WebSocket (or SSE) endpoint, handled by a new StreamingPipelineService. PipelineService.process() and all Sprint 01 endpoints stay untouched. No VAD yet — just get audio chunks flowing to a service that can emit events.
Verify: the new endpoint accepts a live/chunked audio stream and the streaming service receives chunks; the existing synchronous /pipeline/* path is unchanged and still green.

T6 — VAD endpointing + partial events

On the streaming transport from T5, add Silero VAD (ONNX, CPU, executor-offloaded) to auto-detect end-of-turn, and emit partial ASR / translation events to the UI as they become available; final TTS still returns via the existing WAV transport. Single speaker; no overlap handling. (T5+T6 together are what produce real automatic turn-taking — detecting silence inside a completed upload does not.)
Verify: speaking with a natural trailing pause auto-fires the turn without a manual Stop; the UI shows transcript/translation text updating before audio finishes.

T7 — Extended metrics (additive only)

Extend MetricsResponse with new backward-compatible fields — RTF, backend, model identity, per-utterance timing — leaving existing request-count and aggregate-latency fields intact. Log real per-stage latency/RTF when stages are real.
Verify: /metrics still returns the original fields plus the new ones; real timings appear when stages are real. Add # NOTE: tiny-model / CPU timings are not representative of the target card.

T8 — Eval harness

Add scripts/eval that runs the committed fixtures/dialogues through the pipeline and prints a table: meaning/accuracy score (BLEU or COMET-lite if available, else placeholder) + per-stage RTF + total latency, scored against the ground-truth transcripts/translations in the fixtures README. Parameterize by backend/model so the same command benchmarks tiny-now and real-later.
Verify: one command produces the table on the committed fixtures.

TTS this sprint (deferred, explicit)

Real TTS is out of scope for Sprint 02. TTS_MODE stays mock throughout; TTS_MODE=real returns a clear configuration error rather than a broken half-path. This is consistent with the standing Vietnamese-TTS quality risk — voice is the shakiest stage and is deliberately deferred. TTS_VOICE is accepted and stored for later.

Fixtures (human-supplied; agent must not fabricate speech)

Real spoken clips are required — synthetic/generated audio cannot validate real ASR. The human records these. Agent references them; if missing at T2, # BLOCKED: and skip ahead.


Path: tests/fixtures/audio/
Format: 16 kHz, mono, WAV (PCM s16le). (Convert if needed: ffmpeg -i in.wav -ar 16000 -ac 1 -c:a pcm_s16le out.wav.)
Minimum set / names: vi_clean_01.wav, en_clean_01.wav, vi_pause_01.wav, en_pause_01.wav (pause clips carry a trailing silence for T6). Optional: vi_noise_01.wav, en_noise_01.wav.
Ground truth: tests/fixtures/audio/README.md lists, per clip: what was said (source transcript) and the correct translation. The eval harness (T8) scores against this. Without it, T8 can run but cannot measure accuracy.
Privacy: clips are scripted, non-sensitive business sentences in the recorder's own voice — safe to commit publicly. At least one VN and one EN clip should contain a business/deal term so the glossary hook has real input.


Critical warning — tiny-model latency is throwaway

Tiny-model / CPU numbers prove the workflow is correct; they say nothing about whether the real model on the RTX 4060 hits the sub-2s budget. Never populate a "budget met" claim from tiny/CPU runs. The real latency assessment happens when the chosen model runs on the target card (INFERENCE_BACKEND=cuda). Mark tiny/CPU eval output explicitly non-representative.

Definition of done


Config switches + dependency groups work; fresh clone boots on defaults with no CUDA and no model downloads.
Real ASR and MT satisfy the existing contracts (additive endpoints only) and run bidirectionally on tiny/available models, with inference offloaded off the event loop.
Streaming transport + VAD endpointing + partial events implemented via a separate StreamingPipelineService; PipelineService.process() and Sprint 01 endpoints untouched.
Glossary hook works; MetricsResponse extended additively; eval harness runs on committed fixtures.
Real TTS deferred; TTS_MODE=real errors clearly.
Swapping to the final model = env changes only (ASR_MODEL, MT_MODEL, *_MODE=real, INFERENCE_BACKEND=cuda) — no code change.
ruff, pytest, docker compose build, and apps/web build all green.


Out of scope — refuse on sight

Cloud inference · training/fine-tuning · ROCm · real TTS · overlap/multi-speaker diarization · extra language pairs · UI redesign beyond dual-view + streaming text · incompatible contract changes · committing model weights.

What to leave for the human (do not attempt)


Choosing/downloading the final ASR/MT checkpoints.
Recording the audio fixtures and writing the ground-truth README.
The real accuracy/latency benchmark on the RTX 4060.
The production glossary content and full test-dialogue set (agent commits small placeholders only).
