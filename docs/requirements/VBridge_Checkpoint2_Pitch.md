# VBridge — Privacy-First AI Interpreter for Real-Time Vietnamese–English Business Meetings
### Checkpoint 2 Submission · Vietnam AI Innovation Challenge (Sponsored by AI Singapore)

---

## 1. What are we building?

VBridge is a real-time, bidirectional AI interpreter for **in-person Vietnamese–English business meetings** — negotiations, partnership talks, and contract discussions — that runs entirely **on-device, with no cloud dependency**.

Unlike translation apps that process one isolated sentence at a time, VBridge is built for live, unscripted, multi-turn conversation. It continuously listens, detects speaker turns, transcribes speech, translates it incrementally, and returns the translation with minimal interruption to the meeting's natural rhythm.

The system is a decoupled four-stage pipeline:

- **Speech Recognition (ASR)** — open-source Whisper / PhoWhisper convert live speech to text while handling conversational turn-taking and background noise.
- **Machine Translation (MT)** — a **distilled, task-focused translation engine** (built on open models such as NLLB-200-distilled) tuned for business dialogue, delivering fast, context-aware translation with consistent terminology.
- **Streaming Text-to-Speech (TTS)** — synthesized speech is produced as soon as translated text is available, reducing *perceived* latency and preserving conversational flow. Where a language's TTS quality isn't meeting-grade, VBridge falls back to clear on-screen text — the challenge accepts either.
- **Conversation Memory** — recent dialogue is retained so context, company/product names, and negotiated terms stay consistent across turns, rather than each sentence being translated in isolation.

The pipeline runs on accessible hardware — laptop, tablet, or a compact edge device — and is engineered for genuinely low perceived latency, targeting a **sub-2-second response** on natural turns.

## 2. Who is it for?

VBridge is built for organizations that need communication that is **fast, private, and reliable at the same time**:

- Vietnamese and Singaporean business delegations
- Corporate negotiations and investment / partnership meetings
- Government and enterprise collaborations
- Any meeting touching confidential or commercially sensitive information

In these settings, a professional interpreter is expensive and hard to schedule on short notice — while routing deal terms, financials, and strategy through third-party cloud translation APIs is an unacceptable confidentiality risk. VBridge lets both sides talk naturally without trading away privacy or responsiveness.

## 3. What makes VBridge different?

Existing tools fall into two camps: **cloud translators** that transmit meeting audio to external servers (a non-starter for confidential talks), and **general-purpose apps** that translate isolated sentences slowly and blindly to context. VBridge is built around four innovations that answer both:

**Privacy-first architecture.** 100% on-device / on-premise inference on open models — no audio or transcript ever leaves the room. This is the one property generic cloud tools *structurally cannot* offer.

**Distillation-driven low latency.** Instead of a heavy general-purpose model, VBridge runs a distilled, task-specific translation engine for Vietnamese–English business dialogue. Knowledge distillation for edge deployment is a technique **our team has already shipped in production**, not a theoretical claim — which is why we target real low latency, not a best-effort cloud call.

**Context-aware translation.** Conversation memory plus a business glossary keep terminology stable: company names, product names, and deal terms translate the same way every time they appear, reducing misunderstanding during negotiation. This directly protects meaning and intent — the heart of translation accuracy.

**Modular, extensible design.** ASR, MT, TTS, and memory are independently swappable. Adding a new language pair — including lower-resource languages — is a configuration change, not a redesign.

## Closing

VBridge is more than a translation app — it is a **privacy-first AI meeting assistant** that unifies speech recognition, distilled machine translation, streaming synthesis, and conversational context into one deployable system. By putting confidentiality, low latency, and natural interaction first, VBridge makes multilingual business communication feel as seamless as speaking the same language.
