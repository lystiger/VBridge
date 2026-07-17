import asyncio

from shared.schemas import MetricsResponse, PipelineResponse


class MetricsCollector:
    def __init__(
        self,
        backend: str = "cpu",
        asr_model: str = "mock",
        mt_model: str = "mock",
        asr_mode: str = "mock",
        mt_mode: str = "mock",
    ) -> None:
        self._count = 0
        self._totals = {
            "asr_ms": 0.0,
            "translation_ms": 0.0,
            "tts_ms": 0.0,
            "total_pipeline_ms": 0.0,
        }
        self._lock = asyncio.Lock()
        self.backend = backend
        self.asr_model = asr_model
        self.mt_model = mt_model
        self.asr_mode = asr_mode
        self.mt_mode = mt_mode
        self._recent: list[dict[str, float | str]] = []

    async def record(
        self, result: PipelineResponse, audio_duration_ms: float | None = None
    ) -> None:
        async with self._lock:
            self._count += 1
            for field in self._totals:
                self._totals[field] += getattr(result, field)
            utterance: dict[str, float | str] = {
                "session_id": result.session_id,
                "asr_ms": result.asr_ms,
                "translation_ms": result.translation_ms,
                "tts_ms": result.tts_ms,
                "total_pipeline_ms": result.total_pipeline_ms,
                "backend": self.backend,
                "asr_model": self.asr_model,
                "mt_model": self.mt_model,
                "asr_mode": self.asr_mode,
                "mt_mode": self.mt_mode,
            }
            if audio_duration_ms and audio_duration_ms > 0:
                utterance["audio_duration_ms"] = audio_duration_ms
                utterance["asr_rtf"] = result.asr_ms / audio_duration_ms
            self._recent.append(utterance)
            self._recent = self._recent[-100:]

    def snapshot(self) -> MetricsResponse:
        divisor = self._count or 1
        return MetricsResponse(
            request_count=self._count,
            successful_requests=self._count,
            backend=self.backend,
            asr_model=self.asr_model,
            mt_model=self.mt_model,
            asr_mode=self.asr_mode,
            mt_mode=self.mt_mode,
            recent_utterances=self._recent.copy(),
            **{field: value / divisor for field, value in self._totals.items()},
        )
