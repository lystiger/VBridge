from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

PROTOCOL_VERSION = "1.0.0"
ProtocolVersion = Literal["1.0.0"]

Language = Literal["vi", "en"]

# Which side runs the AI pipeline for a room.
#  - "server": this host transcribes/translates; phones are thin clients (Scenario 2).
#  - "device": phones self-infer on-device and the host only relays results (Scenario 1).
InferenceMode = Literal["server", "device"]


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
    is_owner: bool = False


class CreateRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    display_name: str = Field(min_length=1, max_length=80)
    source_language: Language
    target_language: Language
    # Only honored on room creation; the room's mode is fixed for its lifetime.
    inference_mode: InferenceMode = "server"


class JoinRoomRequest(CreateRoomRequest):
    room_code: str = Field(min_length=6, max_length=6)


class RoomAccessResponse(BaseModel):
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    room_id: str
    room_code: str
    status: RoomStatus
    inference_mode: InferenceMode = "server"
    participant: RoomParticipant
    access_token: str
    expires_at: datetime


class RoomStateResponse(BaseModel):
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    room_id: str
    room_code: str
    status: RoomStatus
    inference_mode: InferenceMode = "server"
    participant_count: int = Field(ge=0, le=2)
    participants: list[RoomParticipant]
    expires_at: datetime


class RoomEvent(BaseModel):
    """Common server-event envelope.

    Client events are parsed with ``ClientRoomEventAdapter`` below so their
    payloads are validated by event type rather than accepted as arbitrary JSON.
    """

    model_config = ConfigDict(extra="forbid")

    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    type: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=128)
    room_id: str = Field(min_length=1)
    participant_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class EmptyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParticipantReadyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_received_room_sequence: int = Field(default=0, ge=0)


class AudioStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_format: Literal["pcm_s16le"]
    sample_rate_hz: Literal[16000]
    channels: Literal[1]
    source_language: Language
    target_language: Language


class DeviceTranslationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_language: Language
    target_language: Language
    source_text: str = Field(min_length=1)
    translated_text: str
    asr_latency_ms: float | None = Field(default=None, ge=0)
    mt_latency_ms: float | None = Field(default=None, ge=0)
    end_to_end_latency_ms: float | None = Field(default=None, ge=0)
    audio_duration_ms: float | None = Field(default=None, ge=0)


class ClientEventBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    event_id: str = Field(min_length=1, max_length=128)
    room_id: str = Field(min_length=1)
    participant_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    timestamp: datetime


class ParticipantReadyEvent(ClientEventBase):
    type: Literal["participant.ready"]
    payload: ParticipantReadyPayload = Field(default_factory=ParticipantReadyPayload)


class PingEvent(ClientEventBase):
    type: Literal["ping"]
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class AudioStartEvent(ClientEventBase):
    type: Literal["audio.start"]
    payload: AudioStartPayload


class AudioEndEvent(ClientEventBase):
    type: Literal["audio.end"]
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class DeviceTranslationEvent(ClientEventBase):
    type: Literal["translation.result"]
    payload: DeviceTranslationPayload


ClientRoomEvent = Annotated[
    ParticipantReadyEvent | PingEvent | AudioStartEvent | AudioEndEvent | DeviceTranslationEvent,
    Field(discriminator="type"),
]
ClientRoomEventAdapter: TypeAdapter[ClientRoomEvent] = TypeAdapter(ClientRoomEvent)


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
    room_metrics: dict[str, int | float] = {}
    room_latency_observations: list[dict[str, float]] = []
