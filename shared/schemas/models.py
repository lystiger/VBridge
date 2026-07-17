from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["vi", "en"]


class AudioRequest(BaseModel):
    session_id: str = Field(min_length=1)
    speaker: str = Field(min_length=1)
    language: Language | None = None
    audio_path: str = Field(min_length=1)


class ASRResponse(BaseModel):
    session_id: str
    speaker: str
    source_language: Language
    text: str
    processing_ms: float = Field(ge=0)


class TranslationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_language: Language
    target_language: Language | None = None


class TranslationResponse(BaseModel):
    session_id: str
    source_language: Language
    target_language: Language
    source_text: str
    translated_text: str
    processing_ms: float = Field(ge=0)


class TTSRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    language: Language


class TTSResponse(BaseModel):
    session_id: str
    language: Language
    audio_url: str
    audio_format: Literal["wav"] = "wav"
    processing_ms: float = Field(ge=0)


class PipelineResponse(BaseModel):
    request_id: str
    session_id: str
    status: Literal["completed"] = "completed"
    transcript: str
    translation: str
    source_language: Language
    target_language: Language
    audio_url: str
    asr_ms: float = Field(ge=0)
    translation_ms: float = Field(ge=0)
    tts_ms: float = Field(ge=0)
    total_pipeline_ms: float = Field(ge=0)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


class MetricsResponse(BaseModel):
    request_count: int = Field(ge=0)
    successful_requests: int = Field(ge=0)
    asr_ms: float = Field(ge=0)
    translation_ms: float = Field(ge=0)
    tts_ms: float = Field(ge=0)
    total_pipeline_ms: float = Field(ge=0)
