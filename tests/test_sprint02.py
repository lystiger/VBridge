import struct
from pathlib import Path

import pytest

from apps.api.dependencies import get_pipeline_service
from scripts.eval.run import word_error_rate
from services.asr import MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.streaming import StreamingPipelineService
from services.translation import MockTranslationService
from services.tts import MockTTSService
from services.vad import EnergyVAD, SileroVAD
from shared.config import Settings, get_settings
from shared.schemas import PipelineResponse, TranslationRequest


def test_sprint02_configuration_defaults_to_cpu_mocks() -> None:
    settings = Settings(_env_file=None)
    assert settings.inference_backend == "cpu"
    assert settings.asr_mode == settings.mt_mode == settings.tts_mode == "mock"


def test_room_deployment_rejects_unsafe_production_settings() -> None:
    with pytest.raises(ValueError, match="non-default"):
        Settings(_env_file=None, deployment_environment="production")
    with pytest.raises(ValueError, match="must be 1"):
        Settings(_env_file=None, api_workers=2)
    production = Settings(
        _env_file=None,
        deployment_environment="production",
        room_token_secret="a-unique-production-secret",
    )
    assert production.deployment_environment == "production"


def test_real_tts_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VBRIDGE_TTS_MODE", "real")
    get_settings.cache_clear()
    get_pipeline_service.cache_clear()
    with pytest.raises(RuntimeError, match="deferred"):
        get_pipeline_service()
    monkeypatch.delenv("VBRIDGE_TTS_MODE")
    get_settings.cache_clear()
    get_pipeline_service.cache_clear()


@pytest.mark.asyncio
async def test_glossary_is_consistent(tmp_path: Path) -> None:
    glossary = tmp_path / "glossary.csv"
    glossary.write_text("term_src,term_tgt\nlogistics,logistics\n", encoding="utf-8")
    service = MockTranslationService(glossary)
    request = TranslationRequest(session_id="one", text="ngành logistics", source_language="vi")
    first = await service.translate(request)
    second = await service.translate(request)
    assert first.translated_text == second.translated_text
    assert "logistics" in first.translated_text


@pytest.mark.asyncio
async def test_streaming_service_detects_trailing_silence(tmp_path: Path) -> None:
    pipeline = PipelineService(MockASRService(), MockTranslationService(), MockTTSService(tmp_path))
    service = StreamingPipelineService(pipeline, tmp_path / "streams", EnergyVAD())
    loud = struct.pack("<1600h", *([2000] * 1600))
    silence = bytes(3200)
    chunks = iter([loud, *([silence] * 8)])
    events: list[dict[str, object]] = []

    async def receive() -> bytes | None:
        return next(chunks, None)

    async def send(event: dict[str, object]) -> None:
        events.append(event)

    await service.run(receive, send, "stream-test", "vi")
    assert any(event["type"] == "turn.detected" for event in events)
    assert any(event["type"] == "turn.completed" for event in events)


@pytest.mark.asyncio
async def test_silero_vad_detects_business_fixture() -> None:
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("silero_vad")

    samples, _ = sf.read("tests/fixtures/audio_processed/en_business_01.wav", dtype="int16")
    detector = SileroVAD(threshold=0.3, min_silence_ms=100)
    pcm = samples.tobytes()
    detected = False
    for offset in range(0, len(pcm), 1024):
        detected = await detector.feed(pcm[offset : offset + 1024]) or detected
    assert detected


@pytest.mark.asyncio
async def test_metrics_calculates_rtf_and_tags() -> None:
    collector = MetricsCollector("cpu", "tiny", "mock", "real", "mock")
    result = PipelineResponse(
        request_id="r",
        session_id="s",
        transcript="Hello",
        translation="Xin chào",
        source_language="en",
        target_language="vi",
        audio_url="/a.wav",
        asr_ms=500,
        translation_ms=10,
        tts_ms=5,
        total_pipeline_ms=515,
    )
    await collector.record(result, audio_duration_ms=2000)
    recent = collector.snapshot().recent_utterances[0]
    assert recent["asr_rtf"] == 0.25
    assert recent["asr_mode"] == "real"


def test_word_error_rate() -> None:
    assert word_error_rate("hello world", "hello world") == 0
    assert word_error_rate("hello world", "hello") == 0.5
