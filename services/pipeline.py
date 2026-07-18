import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from services.asr import ASRService
from services.translation import TranslationService
from services.tts import TTSService
from shared.logging import log_event
from shared.schemas import AudioRequest, Language, PipelineResponse, TranslationRequest, TTSRequest


class PipelineOverloadedError(RuntimeError):
    """Raised when inference capacity cannot be acquired within the queue budget."""


class PipelineService:
    def __init__(
        self,
        asr: ASRService,
        translation: TranslationService,
        tts: TTSService,
        max_concurrency: int = 1,
        queue_timeout_seconds: float = 2.0,
    ) -> None:
        self.asr = asr
        self.translation = translation
        self.tts = tts
        self.max_concurrency = max_concurrency
        self.queue_timeout_seconds = queue_timeout_seconds
        self._slots = asyncio.Semaphore(max_concurrency)
        self._active = 0
        self._waiting = 0
        self._rejected = 0

    def admission_snapshot(self) -> dict[str, int]:
        return {
            "inference_active": self._active,
            "inference_waiting": self._waiting,
            "inference_capacity": self.max_concurrency,
            "inference_rejected_total": self._rejected,
        }

    @asynccontextmanager
    async def admission(self) -> AsyncIterator[None]:
        """Acquire one global model-execution slot or reject after the queue budget."""

        self._waiting += 1
        try:
            try:
                await asyncio.wait_for(
                    self._slots.acquire(), timeout=self.queue_timeout_seconds
                )
            except TimeoutError as exc:
                self._rejected += 1
                raise PipelineOverloadedError(
                    "inference capacity is temporarily exhausted"
                ) from exc
        finally:
            self._waiting -= 1
        self._active += 1
        try:
            yield
        finally:
            self._active -= 1
            self._slots.release()

    async def process(
        self,
        request: AudioRequest,
        request_id: str | None = None,
        target_language: Language | None = None,
    ) -> PipelineResponse:
        async with self.admission():
            return await self._process(request, request_id, target_language)

    async def _process(
        self,
        request: AudioRequest,
        request_id: str | None = None,
        target_language: Language | None = None,
    ) -> PipelineResponse:
        request_id = request_id or str(uuid4())
        started = perf_counter()
        context = {"request_id": request_id, "session_id": request.session_id}
        log_event("pipeline_started", **context)

        transcript = await self.asr.transcribe(request)
        log_event("asr_completed", duration_ms=transcript.processing_ms, **context)
        translation = await self.translation.translate(
            TranslationRequest(
                session_id=request.session_id,
                text=transcript.text,
                source_language=transcript.source_language,
                target_language=target_language,
            )
        )
        log_event("translation_completed", duration_ms=translation.processing_ms, **context)
        speech = await self.tts.synthesize(
            TTSRequest(
                session_id=request.session_id,
                text=translation.translated_text,
                language=translation.target_language,
            )
        )
        log_event("tts_completed", duration_ms=speech.processing_ms, **context)
        total_ms = (perf_counter() - started) * 1000
        log_event("pipeline_finished", duration_ms=total_ms, **context)
        return PipelineResponse(
            request_id=request_id,
            session_id=request.session_id,
            transcript=transcript.text,
            translation=translation.translated_text,
            source_language=transcript.source_language,
            target_language=translation.target_language,
            audio_url=speech.audio_url,
            asr_ms=transcript.processing_ms,
            translation_ms=translation.processing_ms,
            tts_ms=speech.processing_ms,
            total_pipeline_ms=total_ms,
        )
