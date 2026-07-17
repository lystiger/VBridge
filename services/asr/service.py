from abc import ABC, abstractmethod
from time import perf_counter

from shared.schemas import ASRResponse, AudioRequest


class ASRService(ABC):
    @abstractmethod
    async def transcribe(self, request: AudioRequest) -> ASRResponse: ...


class MockASRService(ASRService):
    async def transcribe(self, request: AudioRequest) -> ASRResponse:
        started = perf_counter()
        language = request.language or "vi"
        text = "Xin chào" if language == "vi" else "Hello"
        return ASRResponse(
            session_id=request.session_id,
            speaker=request.speaker,
            source_language=language,
            text=text,
            processing_ms=(perf_counter() - started) * 1000,
        )
