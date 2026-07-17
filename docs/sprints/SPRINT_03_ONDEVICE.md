# VBridge Sprint 03 — On-Device Android Foundation

**Phone track · Sprint 1** · Branch: `spike/android-on-device`

## Goal

Answer the one question that decides the entire on-device pivot, then — **only if it passes** — lay the native foundation.

> Can the target phone run ASR on-device at tolerable latency?

This sprint is **gate-driven**. The proof-of-life decision is the primary deliverable; every downstream item is conditional on it. We do not build the house before the floor is proven.

## Context

- **`main` is the guaranteed fallback demo** — the laptop web build (Sprint 02) stays demo-stable and **untouched** for the whole sprint.
- **This branch is the fully on-device Android pivot** — judges see it on a phone; ASR/MT/TTS run on-device with no server.
- **Decided:** Android · spike-first · off-ramp = phone-as-thin-client to a local backend over LAN.
- Full spike spec: [android_on_device_spike.md](../spikes/android_on_device_spike.md).

---

## Success Criteria

By the end of Sprint 03:

- The proof-of-life **gate is answered with real device numbers** (RTF for EN **and** VI, memory, 10-run thermal, HyperOS lockscreen survival).
- A **Go / No-Go is recorded** against the gate, with rationale.
- **If GO:** native Android skeleton committed + the stage contract frozen as a language-agnostic spec.
- **If NO-GO:** the thin-client off-ramp is documented and becomes the plan.
- **`main` untouched**; the laptop demo still runs green.

---

## Non-Negotiables (inherited from CLAUDE.md)

1. **On-device only.** No cloud/hosted inference in the translation path.
2. **No training or fine-tuning.** Load pre-existing/quantized models only.
3. **Do not touch `main`.** The laptop web build is the fallback demo — keep it stable and committed.
4. **No model weights committed.** Weights load from device storage via `adb push`; never into git.
5. **Demo is the north star.** A marginal on-device result that risks the demo loses to the stable laptop fallback.

---

## Tech Stack

- **Android:** Kotlin · Gradle · minSdk 26 · `arm64-v8a`
- **Inference:** sherpa-onnx (bundled ONNX Runtime) · **Whisper-tiny int8** (~75 MB)
- **Measurement inputs:** the committed 16 kHz fixtures (`tests/fixtures/audio_processed/`) for a repeatable, eval-comparable RTF + live mic as secondary
- **Reference / eval:** the existing Python backend, unchanged, on the good machine — it is the model-selection lab, not part of the phone path

---

## Sprint Deliverables

### 1. Proof-of-Life benchmark app
sherpa-onnx + Whisper-tiny int8, per the spike spec. Runtime `RECORD_AUDIO` permission; models/fixtures loaded from the app-specific external dir (no storage-permission grants).

### 2. Device measurement report
Fill the spike's results table on the **confirmed SoC**: RTF for EN + VI, fixtures + live mic, 2 vs 4 threads, peak memory, RTF drift across a 10-run loop (thermal), and whether the inference thread survives lockscreen (HyperOS).

### 3. Go / No-Go decision
Score against the continuous gate: **< 0.30 proceed · 0.30–0.50 marginal · > 0.50 off-ramp.** Record the decision + reasoning in the spike doc.

### 4. [If GO] Contract freeze
Extract the stage contract — ASR / MT / TTS / VAD interfaces + the event protocol — from `shared/schemas` into a **language-agnostic spec** so the Python reference impl and the phone-native impl cannot drift.

### 5. [If GO] Native Android skeleton
A Kotlin app that runs the PoL path end-to-end (mic → on-device ASR → text on screen), structured so MT and TTS drop in next sprint without a rewrite.

### 6. [If NO-GO] Off-ramp plan
Document phone-as-thin-client: phone runs mic + UI, a mini-PC/laptop in the room runs the pipeline over LAN, reusing the existing WebSocket streaming path. Still on-device / no cloud — the compute just isn't in the phone.

---

## NOT INCLUDED — defer to Sprint 04+

- MT and TTS **on device** (next, only if the gate passes)
- Model selection / accuracy tuning (that's the good-machine eval lab)
- Streaming turn-taking / VAD endpointing on the phone
- iOS
- UI polish beyond a benchmark trigger + log
- **Any change to `main` or the laptop pipeline**

---

## Risks (call them early)

- **Tiny latency ≠ the VI model you'll ship.** Whisper-tiny has poor Vietnamese WER; the model VI accuracy actually needs is 2–4× slower. A passing tiny RTF proves *capability*, not the production number. The real gate is "can the phone clear RTF with the smallest model that gives usable VI accuracy," and that isn't fully answerable until the good machine picks that model.
- **Mid-range silicon.** If the Note 14 is a Helio G99 / Dimensity 7025-class SoC, `< 0.30` is optimistic — expect "marginal," and don't read marginal as failure.
- **HyperOS background kill.** Xiaomi aggressively freezes/kills background threads on lockscreen — a real threat to a live meeting app. It's a **gate metric**, not an afterthought.
- **Accuracy vs on-device trade-off.** Accuracy is 30% of the rubric; on-device forces small models. This sprint spends accuracy to buy the on-device story — a conscious bet, not a free win.

---

## Definition of Done

Sprint 03 is complete when:

- The gate is answered with **real numbers on the confirmed SoC** (not emulator, not estimates).
- A **Go / No-Go is recorded** with decision + rationale.
- The branch is committed in a **known-good state**; `main` is untouched and still green.
- **If GO:** the frozen contract spec and native skeleton are committed.
- **If NO-GO:** the thin-client off-ramp is documented as the forward plan.

Nothing else. The point of this sprint is a **decision**, backed by evidence.

---

## Owners

- **MLOps** — Android build, device measurement, gate execution.
- **AI eng** — VI/EN transcript sanity; owns the "tiny vs base/PhoWhisper" model-headroom judgment feeding the good-machine eval.
- **Data eng** — fixtures already serve the spike; begins glossary + eval prep for on-device MT.
