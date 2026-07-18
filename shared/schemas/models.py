from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

Language = Literal["vi", "en"]


class RoomStatus(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class RoomParticipant(BaseModel):
    participant_id: str
    display_name: str
    source_language: Language
    target_language: Language
    connected: bool = False


class CreateRoomRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    source_language: Language
    target_language: Language


class JoinRoomRequest(CreateRoomRequest):
    room_code: str = Field(min_length=6, max_length=6)


class RoomAccessResponse(BaseModel):
    room_id: str
    room_code: str
    status: RoomStatus
    participant: RoomParticipant
    access_token: str
    expires_at: datetime


class RoomStateResponse(BaseModel):
    room_id: str
    room_code: str
    status: RoomStatus
    participant_count: int = Field(ge=0, le=2)
    participants: list[RoomParticipant]
    expires_at: datetime


class RoomEvent(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=128)
    room_id: str = Field(min_length=1)
    participant_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


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


class SessionCreateResponse(BaseModel):
    session_id: str


class ParticipantJoinRequest(BaseModel):
    participant_id: str | None = None
    source_language: Language
    target_language: Language


class ParticipantResponse(BaseModel):
    session_id: str
    participant_id: str
    source_language: Language
    target_language: Language
    connected: bool = False


class TurnStartRequest(BaseModel):
    type: Literal["turn.start"]
    sequence: int = Field(ge=1)
    source_language: Language
    target_language: Language


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
    queue_ms: float = Field(ge=0, default=0)
    mt_ms: float = Field(ge=0, default=0)
    dispatch_ms: float = Field(ge=0, default=0)
    end_to_end_ms: float = Field(ge=0, default=0)
    backend: str = "cpu"
    asr_model: str = "mock"
    mt_model: str = "mock"
    asr_mode: str = "mock"
    mt_mode: str = "mock"
    timing_note: str = "Tiny-model / CPU timings are not representative of the target card."
    recent_utterances: list[dict[str, float | str]] = []
