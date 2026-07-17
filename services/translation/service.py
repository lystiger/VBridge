from abc import ABC, abstractmethod
from time import perf_counter

from shared.schemas import TranslationRequest, TranslationResponse


class TranslationService(ABC):
    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResponse: ...


class MockTranslationService(TranslationService):
    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        started = perf_counter()
        target = request.target_language or ("en" if request.source_language == "vi" else "vi")
        translations = {("Xin chào", "en"): "Hello", ("Hello", "vi"): "Xin chào"}
        translated = translations.get((request.text, target), f"[{target}] {request.text}")
        return TranslationResponse(
            session_id=request.session_id,
            source_language=request.source_language,
            target_language=target,
            source_text=request.text,
            translated_text=translated,
            processing_ms=(perf_counter() - started) * 1000,
        )
