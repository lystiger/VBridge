import asyncio

from shared.schemas import MetricsResponse, PipelineResponse


class MetricsCollector:
    def __init__(self) -> None:
        self._count = 0
        self._totals = {
            "asr_ms": 0.0,
            "translation_ms": 0.0,
            "tts_ms": 0.0,
            "total_pipeline_ms": 0.0,
        }
        self._lock = asyncio.Lock()

    async def record(self, result: PipelineResponse) -> None:
        async with self._lock:
            self._count += 1
            for field in self._totals:
                self._totals[field] += getattr(result, field)

    def snapshot(self) -> MetricsResponse:
        divisor = self._count or 1
        return MetricsResponse(
            request_count=self._count,
            successful_requests=self._count,
            **{field: value / divisor for field, value in self._totals.items()},
        )
