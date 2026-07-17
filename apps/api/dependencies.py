from functools import lru_cache

from services.asr import FasterWhisperASRService, MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.translation import MockTranslationService, NLLBTranslationService
from services.tts import MockTTSService
from shared.config import get_settings


@lru_cache
def get_pipeline_service() -> PipelineService:
    settings = get_settings()
    if settings.tts_mode == "real":
        raise RuntimeError("TTS_MODE=real is unavailable: real TTS is deferred")
    asr = (
        FasterWhisperASRService(settings.asr_model, settings.inference_backend)
        if settings.asr_mode == "real"
        else MockASRService()
    )
    translation = (
        NLLBTranslationService(
            settings.mt_model, settings.inference_backend, settings.glossary_path
        )
        if settings.mt_mode == "real"
        else MockTranslationService(settings.glossary_path)
    )
    return PipelineService(asr, translation, MockTTSService(settings.audio_output_dir))


@lru_cache
def get_metrics_collector() -> MetricsCollector:
    settings = get_settings()
    return MetricsCollector(
        settings.inference_backend,
        settings.asr_model if settings.asr_mode == "real" else "mock",
        settings.mt_model if settings.mt_mode == "real" else "mock",
        settings.asr_mode,
        settings.mt_mode,
    )
