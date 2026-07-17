"""Sprint 02 ASR/MT fixture evaluation harness."""

import argparse
import asyncio
import re
import sys
import wave
from pathlib import Path

from services.asr import FasterWhisperASRService, MockASRService
from services.translation import MockTranslationService, NLLBTranslationService
from shared.config import Settings
from shared.schemas import AudioRequest, TranslationRequest

FIXTURES = [
    ("vi_clean_01.wav", "vi", "Xin chào", "Hello"),
    ("en_clean_01.wav", "en", "Hello", "Xin chào"),
    (
        "vi_business_01.wav",
        "vi",
        "Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions.",
        "Hello, I'm Minh, representing TechViet Solutions.",
    ),
    (
        "en_business_01.wav",
        "en",
        "Hello, I'm Minh, representing TechViet Solutions.",
        "Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions.",
    ),
]


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected, actual = words(reference), words(hypothesis)
    row = list(range(len(actual) + 1))
    for index, expected_word in enumerate(expected, 1):
        next_row = [index]
        for other, actual_word in enumerate(actual, 1):
            next_row.append(
                min(
                    next_row[-1] + 1,
                    row[other] + 1,
                    row[other - 1] + (expected_word != actual_word),
                )
            )
        row = next_row
    return row[-1] / max(len(expected), 1)


async def evaluate(settings: Settings) -> None:
    from sacrebleu import sentence_bleu

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path("tests/fixtures/audio_processed")
    asr = (
        FasterWhisperASRService(settings.asr_model, settings.inference_backend)
        if settings.asr_mode == "real"
        else MockASRService()
    )
    mt = (
        NLLBTranslationService(
            settings.mt_model, settings.inference_backend, settings.glossary_path
        )
        if settings.mt_mode == "real"
        else MockTranslationService(settings.glossary_path)
    )
    print("NOTE: tiny/base CPU timings are non-representative of the target RTX 4060.")
    print(f"backend={settings.inference_backend} asr={settings.asr_model} mt={settings.mt_model}")
    print(f"{'fixture':24} {'WER':>7} {'BLEU':>7} {'RTF':>7} {'total ms':>10}")
    for name, language, source_ref, translation_ref in FIXTURES:
        path = root / name
        with wave.open(str(path), "rb") as audio:
            duration_ms = audio.getnframes() / audio.getframerate() * 1000
        transcript = await asr.transcribe(
            AudioRequest(session_id=name, speaker="eval", language=language, audio_path=str(path))
        )
        translated = await mt.translate(
            TranslationRequest(session_id=name, text=transcript.text, source_language=language)
        )
        wer = word_error_rate(source_ref, transcript.text)
        bleu = sentence_bleu(translated.translated_text, [translation_ref]).score
        rtf = transcript.processing_ms / duration_ms
        total = transcript.processing_ms + translated.processing_ms
        print(f"{name:24} {wer:7.3f} {bleu:7.2f} {rtf:7.3f} {total:10.1f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asr-mode", choices=["mock", "real"])
    parser.add_argument("--asr-model")
    parser.add_argument("--mt-mode", choices=["mock", "real"])
    parser.add_argument("--mt-model")
    parser.add_argument("--backend", dest="inference_backend", choices=["cpu", "cuda"])
    args = parser.parse_args()
    overrides = {key: value for key, value in vars(args).items() if value is not None}
    asyncio.run(evaluate(Settings(**overrides)))


if __name__ == "__main__":
    main()
