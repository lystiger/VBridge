import csv
from abc import ABC, abstractmethod
from asyncio import to_thread
from pathlib import Path
from time import perf_counter

from shared.schemas import TranslationRequest, TranslationResponse


class TranslationService(ABC):
    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResponse: ...


def load_glossary(path: Path | None) -> list[tuple[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [(row["term_src"], row["term_tgt"]) for row in csv.DictReader(handle)]


def apply_glossary(
    source: str, translated: str, language: str, glossary: list[tuple[str, str]]
) -> str:
    for vi_term, en_term in glossary:
        source_term, target_term = (vi_term, en_term) if language == "vi" else (en_term, vi_term)
        if (
            source_term.casefold() in source.casefold()
            and target_term.casefold() not in translated.casefold()
        ):
            translated = f"{translated} [{target_term}]"
    return translated


class MockTranslationService(TranslationService):
    def __init__(self, glossary_path: Path | None = None) -> None:
        self.glossary = load_glossary(glossary_path)

    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        started = perf_counter()
        target = request.target_language or ("en" if request.source_language == "vi" else "vi")
        translations = {("Xin chào", "en"): "Hello", ("Hello", "vi"): "Xin chào"}
        translated = translations.get((request.text, target), f"[{target}] {request.text}")
        translated = apply_glossary(
            request.text, translated, request.source_language, self.glossary
        )
        return TranslationResponse(
            session_id=request.session_id,
            source_language=request.source_language,
            target_language=target,
            source_text=request.text,
            translated_text=translated,
            processing_ms=(perf_counter() - started) * 1000,
        )


class NLLBTranslationService(TranslationService):
    language_codes = {"vi": "vie_Latn", "en": "eng_Latn"}

    def __init__(self, model_name: str, backend: str, glossary_path: Path | None = None) -> None:
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Real MT requires: pip install -e '.[mt]'") from exc
        self.backend = backend
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(backend)
        self.glossary = load_glossary(glossary_path)

    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        return await to_thread(self._translate, request)

    def _translate(self, request: TranslationRequest) -> TranslationResponse:
        started = perf_counter()
        target = request.target_language or ("en" if request.source_language == "vi" else "vi")
        self.tokenizer.src_lang = self.language_codes[request.source_language]
        inputs = self.tokenizer(request.text, return_tensors="pt").to(self.backend)
        generated = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(self.language_codes[target]),
        )
        translated = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        translated = apply_glossary(
            request.text, translated, request.source_language, self.glossary
        )
        return TranslationResponse(
            session_id=request.session_id,
            source_language=request.source_language,
            target_language=target,
            source_text=request.text,
            translated_text=translated,
            processing_ms=(perf_counter() - started) * 1000,
        )
