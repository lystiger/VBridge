from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ROOM_TOKEN_SECRET = "vbridge-local-room-secret-change-me"
DEFAULT_CONVERSATION_ENCRYPTION_KEY = "vbridge-local-conversation-key-change-me"


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
    deployment_environment: Literal["development", "production"] = "development"
    api_workers: int = Field(default=1, ge=1)
    room_token_secret: str = DEFAULT_ROOM_TOKEN_SECRET
    room_ttl_minutes: int = 30
    room_cleanup_interval_seconds: int = 60
    room_reconnect_grace_seconds: int = 60
    room_max_audio_bytes: int = 10 * 1024 * 1024
    room_max_turn_seconds: int = 30
    room_max_json_bytes: int = 16 * 1024
    room_max_queued_turns: int = 4
    inference_max_concurrency: int = Field(default=1, ge=1, le=32)
    inference_queue_timeout_seconds: float = Field(default=2.0, ge=0.05, le=60)
    conversation_database_path: Path = Path(".runtime/vbridge.db")
    conversation_encryption_key: str = DEFAULT_CONVERSATION_ENCRYPTION_KEY

    @model_validator(mode="after")
    def validate_room_deployment(self) -> "Settings":
        if self.api_workers != 1:
            raise ValueError("room state is process-local; VBRIDGE_API_WORKERS must be 1")
        if (
            self.deployment_environment == "production"
            and self.room_token_secret == DEFAULT_ROOM_TOKEN_SECRET
        ):
            raise ValueError("production requires a non-default VBRIDGE_ROOM_TOKEN_SECRET")
        if (
            self.deployment_environment == "production"
            and self.conversation_encryption_key == DEFAULT_CONVERSATION_ENCRYPTION_KEY
        ):
            raise ValueError(
                "production requires a non-default VBRIDGE_CONVERSATION_ENCRYPTION_KEY"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
