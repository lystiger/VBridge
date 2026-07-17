from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VBRIDGE_", env_file=".env", extra="ignore")

    app_name: str = "VBridge API"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    audio_output_dir: Path = Path(".runtime/audio")
    inference_backend: Literal["cpu", "cuda"] = "cpu"
    asr_mode: Literal["mock", "real"] = "mock"
    asr_model: str = "Systran/faster-whisper-base"
    mt_mode: Literal["mock", "real"] = "mock"
    mt_model: str = "facebook/nllb-200-distilled-600M"
    tts_mode: Literal["mock", "real"] = "mock"
    tts_voice: str = "default"
    glossary_path: Path | None = Path("docs/referrences/glossary.csv")
    vad_mode: Literal["energy", "silero"] = "silero"
    vad_threshold: float = 0.3
    vad_min_silence_ms: int = 500
    partial_interval_chunks: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
