from abc import ABC, abstractmethod
from asyncio import to_thread
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


class FasterWhisperASRService(ASRService):
    def __init__(self, model_name: str, backend: str) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Real ASR requires: pip install -e '.[asr]'") from exc
        compute_type = "int8" if backend == "cpu" else "float16"
        self.model = WhisperModel(model_name, device=backend, compute_type=compute_type)

    async def transcribe(self, request: AudioRequest) -> ASRResponse:
        return await to_thread(self._transcribe, request)

    def _transcribe(self, request: AudioRequest) -> ASRResponse:
        started = perf_counter()
        segments, info = self.model.transcribe(request.audio_path, language=request.language)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        language = request.language or info.language
        if language not in {"vi", "en"}:
            raise ValueError(f"Unsupported detected language: {language}")
        return ASRResponse(
            session_id=request.session_id,
            speaker=request.speaker,
            source_language=language,
            text=text,
            processing_ms=(perf_counter() - started) * 1000,
        )
