from pathlib import Path

import pytest

from services.asr import MockASRService
from services.pipeline import PipelineService
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
