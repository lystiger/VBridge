import wave
from collections.abc import Awaitable, Callable
from pathlib import Path

from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.vad import VoiceActivityDetector
from shared.schemas import AudioRequest, TranslationRequest

EventSender = Callable[[dict[str, object]], Awaitable[None]]


class StreamingPipelineService:
    def __init__(
        self,
        pipeline: PipelineService,
        output_dir: Path,
        vad: VoiceActivityDetector,
        partial_interval: int = 12,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self.pipeline, self.output_dir = pipeline, output_dir
        self.vad, self.partial_interval = vad, partial_interval
        self.metrics = metrics

    async def run(
        self,
        receive: Callable[[], Awaitable[bytes | None]],
        send: EventSender,
        session_id: str,
        language: str,
    ) -> None:
        chunks: list[bytes] = []
        await send({"type": "session.ready", "session_id": session_id})
        while (chunk := await receive()) is not None:
            chunks.append(chunk)
            await send({"type": "audio.received", "sequence": len(chunks)})
            ended = await self.vad.feed(chunk)
            if not ended and len(chunks) % self.partial_interval == 0:
                await self._partial(chunks, send, session_id, language)
            if ended:
                await self._finish(chunks, send, session_id, language)
                chunks = []
                self.vad.reset()
        if chunks:
            await self._finish(chunks, send, session_id, language)

    def _write_wav(self, chunks: list[bytes], session_id: str, suffix: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"stream-{session_id}-{suffix}.wav"
        with wave.open(str(path), "wb") as output:
            output.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            output.writeframes(b"".join(chunks))
        return path

    async def _partial(
        self, chunks: list[bytes], send: EventSender, session_id: str, language: str
    ) -> None:
        path = self._write_wav(chunks, session_id, "partial")
        transcript = await self.pipeline.asr.transcribe(
            AudioRequest(
                session_id=session_id, speaker="speaker_a", language=language, audio_path=str(path)
            )
        )
        if not transcript.text:
            return
        await send({"type": "asr.partial", "text": transcript.text})
        translation = await self.pipeline.translation.translate(
            TranslationRequest(
                session_id=session_id,
                text=transcript.text,
                source_language=transcript.source_language,
            )
        )
        await send({"type": "translation.partial", "text": translation.translated_text})

    async def _finish(
        self, chunks: list[bytes], send: EventSender, session_id: str, language: str
    ) -> None:
        path = self._write_wav(chunks, session_id, "final")
        await send({"type": "turn.detected"})
        result = await self.pipeline.process(
            AudioRequest(
                session_id=session_id, speaker="speaker_a", language=language, audio_path=str(path)
            )
        )
        if self.metrics is not None:
            duration_ms = sum(len(chunk) for chunk in chunks) / 2 / 16_000 * 1000
            await self.metrics.record(result, duration_ms)
        await send({"type": "asr.final", "text": result.transcript})
        await send({"type": "translation.final", "text": result.translation})
        await send(
            {
                "type": "turn.completed",
                "audio_url": result.audio_url,
                "asr_ms": result.asr_ms,
                "translation_ms": result.translation_ms,
                "tts_ms": result.tts_ms,
                "total_pipeline_ms": result.total_pipeline_ms,
            }
        )
