from functools import lru_cache

from services.asr import MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.translation import MockTranslationService
from services.tts import MockTTSService
from shared.config import get_settings


@lru_cache
def get_pipeline_service() -> PipelineService:
    settings = get_settings()
    return PipelineService(
        MockASRService(), MockTranslationService(), MockTTSService(settings.audio_output_dir)
    )


@lru_cache
def get_metrics_collector() -> MetricsCollector:
    return MetricsCollector()
