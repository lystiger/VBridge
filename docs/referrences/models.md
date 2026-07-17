# VBridge — Available Models Catalog

Every model named as a candidate in `vbridge_engineering_report.md`, organized by pipeline stage.

**Scoring lens:** 100% on-device, **CPU-only** (AMD Radeon 780M — no CUDA/ROCm), 48h build. See `../report_feasibility.md` for the reasoning behind the picks.

**Two hard filters applied to everything below:**
- ❌ **Cloud = disqualified.** Any hosted API violates the core constraint. Flagged, not chosen.
- ⚠️ **License.** Several strong models are **CC-BY-NC (non-commercial)**. Fine for a hackathon demo; a blocker if VBridge is ever commercialized. Flagged per row — verify against the repo before shipping.

---

## Stage 0 — Voice Activity Detection (VAD)

| Model | Repo / ID | Runtime | Footprint | CPU on 780M | License | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Silero VAD v5** | `snakers4/silero-vad` | ONNX | ~2 MB | Excellent (<1% core) | MIT | ✅ **Primary** |
| WebRTC VAD | `py-webrtcvad` | C ext | tiny | Trivial | MIT | ⚠️ Fallback only — high false-positives on fan/keyboard noise |
| FunASR FSMN-VAD | `funasr` | ONNX/PyTorch | ~small | OK (~3.5% core) | MIT | ➖ Heavier, more complex chunking. Skip. |

---

## Stage 1 — Automatic Speech Recognition (ASR)

| Model | Repo / ID | Runtime | Footprint (INT8) | CPU on 780M | License | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **faster-whisper base** | `Systran/faster-whisper-base` | CTranslate2 | ~0.15 GB | Good — start here | MIT | ✅ **Start point** |
| **faster-whisper small** | `Systran/faster-whisper-small` | CTranslate2 | ~0.5 GB | OK — climb if headroom | MIT | ✅ Upgrade if budget allows |
| faster-whisper large-v3 / turbo | `Systran/faster-whisper-large-v3` | CTranslate2 | ~1.5 GB | ❌ Blows sub-2s on CPU | MIT | ➖ GPU-only in practice |
| PhoWhisper-small / medium | `vinai/PhoWhisper-small` | PyTorch → convert to CT2 | ~0.5–2.1 GB | Small: OK; medium: tight | Apache-2.0 *(verify)* | ⚠️ Best VI accuracy — use small if VI WER matters |
| Whisper (HF PyTorch) | `openai/whisper-*` | PyTorch | 3.1 GB | ❌ Slow on CPU (RTF ~0.65) | MIT | ➖ Superseded by CT2 build |
| Whisper Streaming (OpenAI API) | hosted | cloud | — | — | — | ❌ **Forbidden — cloud** |

**Note:** on CPU use `compute_type="int8"` — **not** `int8_float16` (that's a CUDA compute type and won't load here).

---

## Stage 2 — Machine Translation (MT)

| Model | Repo / ID | Runtime | Footprint | CPU on 780M | License | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MarianMT / OPUS-MT** | `Helsinki-NLP/opus-mt-vi-en`, `opus-mt-en-vi` | CTranslate2 / Marian | ~0.6 GB (pair) | Excellent (~25 ms) | CC-BY-4.0 | ✅ **Primary** — two dedicated models, no lang-tag routing |
| **NLLB-200-distilled-600M** | `facebook/nllb-200-distilled-600M` | CTranslate2 | ~1.2 GB | OK on CPU | ⚠️ **CC-BY-NC-4.0** | ⚠️ Better code-switching/context — stretch goal, non-commercial |
| M2M100 418M / 1.2B | `facebook/m2m100_418M` | CTranslate2 | 1–2.5 GB | 1.2B slow on CPU | MIT | ➖ NLLB does the same job better |
| SeamlessM4T Medium | `facebook/seamless-m4t-medium` | PyTorch | 4.8 GB | ❌ Too heavy | ⚠️ CC-BY-NC-4.0 | ➖ E2E path — rejected in report §1 |

---

## Stage 3 — Text-to-Speech (TTS)

| Model | Repo / ID | Runtime | Footprint | CPU on 780M | License | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kokoro-82M** | `hexgrad/Kokoro-82M` | ONNX | 82 MB | Excellent (RTF <0.1) | Apache-2.0 | ✅ **English primary** |
| **Piper (vi_VN)** | `rhasspy/piper` | ONNX (C++) | ~50 MB | Excellent | MIT | ✅ **Vietnamese realistic path** — verify voice quality |
| MeloTTS | `myshell-ai/MeloTTS` | PyTorch | 240 MB | OK | MIT | ⚠️ Report claims native VI — **MeloTTS does not officially list Vietnamese.** Verify before relying on it. |
| Coqui XTTS v2 | `coqui/XTTS-v2` | PyTorch | 3.0 GB | ❌ TTFT >800 ms on CPU | ⚠️ CPML (non-commercial) | ➖ Too heavy for real-time |

**Vietnamese TTS is the project's biggest unknown.** If neither Piper vi_VN nor a VI MeloTTS build is meeting-grade on CPU, ship **text-only Vietnamese output** — the challenge accepts it.

---

## Stage 4 — Conversation Memory / Glossary

No model. A dict of pinned terms (company/product names, deal terms) + recent-turn context, applied at the MT boundary. Owned by Data eng. No inference cost.

---

## Recommended default stack (CPU / on-device / 48h)

| Stage | Choice | Fallback |
| :--- | :--- | :--- |
| VAD | Silero VAD v5 (ONNX) | WebRTC VAD |
| ASR | faster-whisper **base**, `int8` | small (if budget), PhoWhisper-small for VI |
| MT | MarianMT OPUS-MT (both directions) | NLLB-600M (non-commercial) |
| TTS (EN) | Kokoro-82M (ONNX) | Piper en_US |
| TTS (VI) | Piper vi_VN | **Text-only fallback** |
| Memory | dict + glossary | — |

All entries run on CPU and offline. No CUDA, no cloud, no training — constraint-clean.

**Before download:** confirm license terms per row (NLLB / SeamlessM4T / XTTS are non-commercial), and confirm Piper vi_VN / MeloTTS actually cover Vietnamese at meeting quality.
