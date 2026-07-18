import asyncio
from pathlib import Path

import pytest

from services.asr import MockASRService
from services.pipeline import PipelineOverloadedError, PipelineService
from services.translation import MockTranslationService
from services.tts import MockTTSService
from shared.schemas import AudioRequest


@pytest.mark.asyncio
async def test_pipeline_returns_complete_result(tmp_path: Path) -> None:
    pipeline = PipelineService(MockASRService(), MockTranslationService(), MockTTSService(tmp_path))
    result = await pipeline.process(
        AudioRequest(
            session_id="session-1", speaker="speaker-a", language="vi", audio_path="audio.wav"
        ),
        request_id="request-1",
    )
    assert result.request_id == "request-1"
    assert result.transcript == "Xin chào"
    assert result.translation == "Hello"
    assert result.target_language == "en"
    assert result.total_pipeline_ms >= result.asr_ms


@pytest.mark.asyncio
async def test_pipeline_rejects_when_global_capacity_wait_expires(tmp_path: Path) -> None:
    class SlowASR(MockASRService):
        async def transcribe(self, request: AudioRequest):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.1)
            return await super().transcribe(request)

    pipeline = PipelineService(
        SlowASR(),
        MockTranslationService(),
        MockTTSService(tmp_path),
        max_concurrency=1,
        queue_timeout_seconds=0.01,
    )
    request = AudioRequest(
        session_id="busy", speaker="speaker", language="vi", audio_path="audio.wav"
    )
    first = asyncio.create_task(pipeline.process(request))
    await asyncio.sleep(0.01)
    with pytest.raises(PipelineOverloadedError):
        await pipeline.process(request)
    await first
    assert pipeline.admission_snapshot() == {
        "inference_active": 0,
        "inference_waiting": 0,
        "inference_capacity": 1,
        "inference_rejected_total": 1,
    }
