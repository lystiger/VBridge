from pathlib import Path

import pytest

from services.asr import MockASRService
from services.translation import MockTranslationService
from services.tts import MockTTSService
from shared.schemas import AudioRequest, TranslationRequest, TTSRequest


@pytest.mark.asyncio
async def test_mock_asr_supports_both_languages() -> None:
    service = MockASRService()
    result = await service.transcribe(
        AudioRequest(session_id="one", speaker="a", language="en", audio_path="x")
    )
    assert result.text == "Hello"


@pytest.mark.asyncio
async def test_mock_translation_switches_direction() -> None:
    result = await MockTranslationService().translate(
        TranslationRequest(session_id="one", text="Hello", source_language="en")
    )
    assert result.target_language == "vi"
    assert result.translated_text == "Xin chào"


@pytest.mark.asyncio
async def test_mock_tts_creates_valid_wav(tmp_path: Path) -> None:
    result = await MockTTSService(tmp_path).synthesize(
        TTSRequest(session_id="one", text="Hello", language="en")
    )
    assert (tmp_path / "one.wav").read_bytes().startswith(b"RIFF")
    assert result.audio_url == "/audio/one.wav"
