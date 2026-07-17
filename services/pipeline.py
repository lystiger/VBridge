from time import perf_counter
from uuid import uuid4

from services.asr import ASRService
from services.translation import TranslationService
from services.tts import TTSService
from shared.logging import log_event
from shared.schemas import AudioRequest, PipelineResponse, TranslationRequest, TTSRequest


class PipelineService:
    def __init__(self, asr: ASRService, translation: TranslationService, tts: TTSService) -> None:
        self.asr = asr
        self.translation = translation
        self.tts = tts

    async def process(
        self, request: AudioRequest, request_id: str | None = None
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
