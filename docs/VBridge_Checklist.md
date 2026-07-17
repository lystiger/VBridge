# VBridge — Local Team Build Checklist

> **Goal:** Build a reliable, low-latency, on-device Vietnamese–English meeting translator for the live hackathon demo.

---

## 0. Non-negotiable MVP

The system must complete this loop reliably:

```text
Microphone
  -> Voice activity / turn detection
  -> ASR
  -> Language direction detection
  -> Translation
  -> TTS or translated text output
  -> Ready for the next speaker
```

### Required demo capabilities

- [ ] Vietnamese -> English
- [ ] English -> Vietnamese
- [ ] Live microphone input
- [ ] Clear source transcript
- [ ] Clear translated output
- [ ] Low perceived latency
- [ ] Push-to-talk fallback
- [ ] Works without a persistent cloud connection
- [ ] Handles at least moderate background noise
- [ ] Runs from one command

### Do not prioritize before the MVP is stable

- Multi-agent architecture
- Full speaker diarization
- Complex model registry
- Large observability stack
- Fancy frontend animation
- Training a new model from scratch
- More than two language directions

---

# 1. Shared Contracts — Do This First

All services must use the same IDs, schemas, timestamps, and error format.

## 1.1 ASR output

```json
{
  "segment_id": "seg-001",
  "speaker": "speaker_a",
  "source_language": "vi",
  "text": "Chúng tôi muốn thảo luận về điều khoản thanh toán.",
  "is_final": true,
  "confidence": 0.91,
  "started_at_ms": 0,
  "ended_at_ms": 2400,
  "processing_ms": 510
}
```

Checklist:

- [ ] Partial and final transcripts are distinguished
- [ ] Every segment has a unique `segment_id`
- [ ] Timestamps use milliseconds
- [ ] Empty or silent audio returns a controlled response
- [ ] Timeout and failure behavior are documented

## 1.2 Translation output

```json
{
  "segment_id": "seg-001",
  "source_language": "vi",
  "target_language": "en",
  "source_text": "Chúng tôi muốn thảo luận về điều khoản thanh toán.",
  "translated_text": "We would like to discuss the payment terms.",
  "model_name": "nllb-student",
  "model_version": "v1",
  "processing_ms": 180
}
```

Checklist:

- [ ] `segment_id` is preserved
- [ ] Both directions are supported
- [ ] Model name and version are recorded
- [ ] Business terms can be overridden by a glossary
- [ ] Failed translation never returns an unexplained blank string

## 1.3 TTS request

```json
{
  "segment_id": "seg-001",
  "text": "We would like to discuss the payment terms.",
  "language": "en",
  "voice": "default",
  "audio_format": "pcm",
  "sample_rate": 16000,
  "streaming": true
}
```

Checklist:

- [ ] One audio format is used everywhere
- [ ] Playback can be interrupted
- [ ] Old audio is cancelled when a newer turn begins
- [ ] Two outputs never speak simultaneously
- [ ] Text-only fallback exists if TTS fails

---

# 2. Member Responsibilities

## AI Engineer 1 — ASR and Turn Detection

### Deliverables

- [ ] Microphone/audio-file input wrapper
- [ ] Voice activity detection
- [ ] Push-to-talk mode
- [ ] Vietnamese ASR
- [ ] English ASR
- [ ] Partial/final transcript support
- [ ] Noise handling baseline
- [ ] ASR benchmark script

### Recommended model path

Start with a reliable baseline:

```text
faster-whisper small / medium
```

Possible Vietnamese comparison:

```text
PhoWhisper
```

### Acceptance criteria

- [ ] Produces stable transcripts in a quiet room
- [ ] Handles numbers, dates, and currencies reasonably
- [ ] Returns final text within an agreed latency target
- [ ] Does not repeatedly emit duplicate segments
- [ ] Push-to-talk works even when automatic turn detection fails

---

## AI Engineer 2 — Translation and Optimization

### Deliverables

- [ ] Vietnamese -> English translation service
- [ ] English -> Vietnamese translation service
- [ ] Business terminology glossary
- [ ] Context window or short conversation memory
- [ ] Model benchmark script
- [ ] Quantized/lightweight inference configuration
- [ ] Optional KD experiment only after the baseline works

### Recommended model path

Start with an existing open model:

```text
NLLB / MarianMT / another tested open MT model
```

### Knowledge distillation rule

KD is optional until the complete system works.

Only proceed when all of these are true:

- [ ] Teacher baseline is working
- [ ] A usable training set exists
- [ ] Student can be trained within available compute/time
- [ ] Quality can be measured
- [ ] Latency reduction can be measured

Required comparison if KD is included:

| Model | Translation quality | Median latency | p95 latency | RAM/VRAM |
|---|---:|---:|---:|---:|
| Teacher | TBD | TBD | TBD | TBD |
| Student | TBD | TBD | TBD | TBD |

Do not claim KD success without numbers.

### Acceptance criteria

- [ ] Both language directions work
- [ ] Important names and numbers are preserved
- [ ] Business glossary remains consistent across turns
- [ ] Empty or failed outputs are handled explicitly
- [ ] Translation latency is logged

---

## Platform/MLOps Lead — Integration and Demo Reliability

### Deliverables

- [ ] Repository structure
- [ ] Shared schemas
- [ ] API/WebSocket orchestration
- [ ] Minimal web UI
- [ ] Docker setup
- [ ] Health checks
- [ ] Structured logging
- [ ] Latency dashboard or summary page
- [ ] CI smoke tests
- [ ] One-command demo launcher
- [ ] Final deployment and backup plan

### Acceptance criteria

- [ ] Full pipeline starts with one command
- [ ] Services expose health endpoints
- [ ] Every request carries a `segment_id`
- [ ] One failed component does not crash the session
- [ ] The pipeline records stage-by-stage latency
- [ ] Demo can recover from a service restart
- [ ] Models are already downloaded before judging

---

# 3. Repository Structure

```text
vbridge/
├── apps/
│   ├── api/
│   └── web/
├── services/
│   ├── asr/
│   ├── translation/
│   ├── tts/
│   └── conversation/
├── shared/
│   ├── schemas/
│   ├── config/
│   └── logging/
├── models/
│   ├── manifests/
│   └── benchmarks/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── latency/
│   └── fixtures/
├── scripts/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

### Git workflow

- [ ] `main` always remains demoable
- [ ] Each member works in a feature branch
- [ ] Pull requests require one teammate review
- [ ] No model weights in Git
- [ ] No secrets in Git
- [ ] Create release tags for stable milestones

Suggested branches:

```text
feat/asr
feat/translation
feat/platform
fix/demo
```

---

# 4. Core Pipeline Rules

```text
Audio input
  -> VAD / push-to-talk
  -> ASR
  -> language direction
  -> translation
  -> terminology correction
  -> TTS/text output
  -> session history
```

Every stage must have:

- [ ] Timeout
- [ ] Structured error response
- [ ] Processing time
- [ ] Model/service version
- [ ] Retry policy where safe
- [ ] Fallback behavior

### Queue rules

- [ ] Audio queue has a maximum size
- [ ] Duplicate segments are ignored
- [ ] Partial transcript is replaceable
- [ ] Final transcript is immutable
- [ ] Stale TTS is cancelled
- [ ] Playback interruption is supported
- [ ] Backpressure is visible in logs

---

# 5. Model Manifest

Create `models/manifests/models.yaml`:

```yaml
asr:
  name: faster-whisper-small
  version: v1
  device: cuda
  compute_type: int8_float16

translation:
  name: nllb-baseline
  version: v1
  source_languages:
    - vi
    - en
  target_languages:
    - en
    - vi

translation_student:
  enabled: false
  name: null
  version: null

tts:
  name: local-tts
  version: v1

runtime:
  demo_profile: gpu
  fallback_profile: cpu
```

Checklist:

- [ ] Record exact model versions
- [ ] Record quantization settings
- [ ] Record hardware requirements
- [ ] Record model licenses
- [ ] Keep a known-good configuration
- [ ] Keep a CPU fallback configuration
- [ ] Freeze model choices before final testing

---

# 6. Latency and Observability

The judging rubric heavily rewards responsiveness and natural meeting flow. Measure the full pipeline, not only model inference.

## Required timings

- [ ] Speech end -> ASR final
- [ ] ASR final -> translation complete
- [ ] Translation complete -> first TTS audio
- [ ] Speech end -> first translated output
- [ ] Full segment completion

Example event:

```json
{
  "event_type": "pipeline_segment",
  "segment_id": "seg-001",
  "source_language": "vi",
  "target_language": "en",
  "asr_ms": 510,
  "translation_ms": 180,
  "tts_first_audio_ms": 220,
  "end_to_first_output_ms": 910,
  "status": "success"
}
```

## Minimum dashboard/summary

- [ ] Median end-to-first-output latency
- [ ] p95 end-to-first-output latency
- [ ] ASR latency
- [ ] Translation latency
- [ ] TTS startup latency
- [ ] Failure count
- [ ] Queue depth
- [ ] Interrupted playback count
- [ ] CPU usage
- [ ] RAM usage
- [ ] GPU memory usage

A simple internal page or JSON summary is enough. Do not overbuild Grafana unless integration is already stable.

---

# 7. Testing Checklist

## Unit tests

- [ ] Schema validation
- [ ] Language direction detection
- [ ] Glossary replacement
- [ ] Queue ordering
- [ ] Duplicate segment rejection
- [ ] Timeout handling
- [ ] Empty audio handling
- [ ] Failed translation handling

## End-to-end tests

- [ ] Vietnamese audio -> English text
- [ ] English audio -> Vietnamese text
- [ ] Vietnamese audio -> English speech
- [ ] English audio -> Vietnamese speech
- [ ] Alternating speakers
- [ ] Quick turn changes
- [ ] User interrupts playback
- [ ] One service restarts
- [ ] CPU-only fallback

## Real-world tests

- [ ] Quiet room
- [ ] Café/background noise
- [ ] Laptop fan noise
- [ ] Speaker close to microphone
- [ ] Speaker far from microphone
- [ ] Vietnamese regional accent
- [ ] Singaporean English accent
- [ ] Fast speaker
- [ ] Long speaker turn
- [ ] False start
- [ ] Self-correction
- [ ] Company names
- [ ] Product names
- [ ] Currency
- [ ] Dates
- [ ] Percentages
- [ ] Contract terminology

---

# 8. Internal Benchmark Set

Create at least:

- [ ] 20 Vietnamese business utterances
- [ ] 20 English business utterances
- [ ] 10 numbers/dates/currency cases
- [ ] 10 company/product-name cases
- [ ] 10 noisy audio cases
- [ ] 10 corrections or false starts

Suggested topics:

```text
Negotiation
Payment terms
Delivery schedules
Pricing
Contract clauses
Technical specifications
Project deadlines
Confidentiality
Investment
Partnership discussions
```

Metrics:

- [ ] ASR word error rate where references exist
- [ ] Translation adequacy score
- [ ] Terminology consistency
- [ ] End-to-first-output latency
- [ ] Failure rate
- [ ] CPU/RAM/VRAM use

---

# 9. Minimal UI

Required interface:

- [ ] Start meeting
- [ ] Stop meeting
- [ ] Push-to-talk
- [ ] Source transcript
- [ ] Translated transcript
- [ ] Source and target language labels
- [ ] Listening status
- [ ] Processing status
- [ ] Speaking status
- [ ] Replay
- [ ] Interrupt playback
- [ ] Offline/local indicator
- [ ] Session history
- [ ] Clear error message

Suggested state machine:

```text
Idle
 -> Listening
 -> Processing
 -> Translating
 -> Speaking
 -> Listening
```

---

# 10. Privacy Requirements

Do not use privacy as a slogan unless it is technically true.

- [ ] Raw audio remains local
- [ ] Transcripts remain local
- [ ] No external analytics SDK
- [ ] Every network dependency is documented
- [ ] Session deletion exists
- [ ] Offline/local status is visible
- [ ] Wi-Fi-off demo is tested in advance
- [ ] Do not claim “100% offline” if any component uses a hosted API

---

# 11. CI/CD

Minimum GitHub Actions pipeline:

```text
Pull request
  -> lint
  -> unit tests
  -> API smoke test
  -> Docker build
```

Checklist:

- [ ] Python linting
- [ ] Type checking
- [ ] Unit tests
- [ ] Docker build test
- [ ] Health endpoint smoke test
- [ ] Dependency caching
- [ ] Failed checks block merge

Release milestones:

```text
v0.1-baseline
v0.2-bidirectional
v0.3-tts
v0.4-demo-safe
v1.0-final
```

---

# 12. Demo Safety

Before judging:

- [ ] All models downloaded
- [ ] Docker images built locally
- [ ] No setup step requires internet
- [ ] Laptop sleep disabled
- [ ] Notifications disabled
- [ ] Devices charged
- [ ] Charger packed
- [ ] Backup microphone/headset available
- [ ] Offline repository copy saved
- [ ] CPU fallback tested
- [ ] Fresh boot -> demo tested
- [ ] One-click launcher tested
- [ ] Primary demo script rehearsed
- [ ] Failure recovery rehearsed

One-command launcher:

```bash
./scripts/start_demo.sh
```

---

# 13. 90-Second Demo Scenario

## Vietnamese speaker

> Chúng tôi đề xuất thời hạn thanh toán là 30 ngày kể từ ngày nhận hàng.

Expected English:

> We propose a payment term of 30 days from the date the goods are received.

## English speaker

> Could you reduce the initial order quantity to five hundred units?

Expected Vietnamese:

> Quý công ty có thể giảm số lượng đơn hàng ban đầu xuống còn 500 sản phẩm không?

Then demonstrate:

- [ ] Quick speaker change
- [ ] One company name
- [ ] One currency value
- [ ] One correction: “Twenty-five, not fifteen.”
- [ ] One technical term from the glossary
- [ ] Playback interruption
- [ ] Local/offline operation
- [ ] Latency metric screen

---

# 14. Hackathon Timeline

## Before the event

- [ ] Repository ready
- [ ] Schemas frozen
- [ ] UI skeleton ready
- [ ] ASR wrapper ready
- [ ] Translation wrapper ready
- [ ] TTS wrapper ready
- [ ] Models cached
- [ ] Benchmark audio prepared
- [ ] Docker baseline tested

## Hours 0–4

- [ ] Confirm hardware
- [ ] Run ASR
- [ ] Run translation
- [ ] Connect ASR -> translation
- [ ] Show translated text
- [ ] Measure baseline latency

## Hours 4–12

- [ ] Add reverse direction
- [ ] Add TTS
- [ ] Add turn segmentation
- [ ] Add structured logs
- [ ] Add timeout and retry behavior
- [ ] Complete first end-to-end demo

## Hours 12–24

- [ ] Add terminology glossary
- [ ] Improve queue behavior
- [ ] Add playback interruption
- [ ] Add session history
- [ ] Add deployment script
- [ ] Record benchmark baseline

## Hours 24–36

- [ ] Test noise
- [ ] Test accents
- [ ] Improve UI
- [ ] Test CPU fallback
- [ ] Fix bottlenecks
- [ ] Freeze model choices

## Final 12 hours

- [ ] No architecture rewrites
- [ ] Run regression tests
- [ ] Produce final benchmark table
- [ ] Record demo video
- [ ] Finalize README
- [ ] Verify public repository
- [ ] Create final release tag
- [ ] Rehearse pitch and recovery plan

---

# 15. Definition of Done

VBridge is demo-ready only when:

- [ ] Both translation directions work
- [ ] Full live pipeline works three times consecutively
- [ ] Push-to-talk fallback works
- [ ] Median and p95 latency are measured
- [ ] Noise test passes acceptably
- [ ] Model and hardware configuration are documented
- [ ] No model download is required during judging
- [ ] One-command startup works
- [ ] CPU or degraded fallback exists
- [ ] Demo script has been rehearsed
- [ ] Team can explain every external dependency
- [ ] Team can prove which parts run locally

---

# Final Priority Order

1. Stable end-to-end pipeline
2. Bidirectional translation
3. Low perceived latency
4. Push-to-talk and interruption handling
5. Business terminology consistency
6. Offline/local deployment proof
7. Robustness under noise
8. Benchmark evidence
9. Minimal clean UI
10. Optional model distillation

> **Rule:** A reliable translator with measured 1–2 second latency is stronger than an ambitious distilled system that fails during the live demonstration.
