import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.schemas import (
    PROTOCOL_VERSION,
    AudioRequest,
    ClientRoomEventAdapter,
    TranslationRequest,
)


def test_audio_request_validates_required_values() -> None:
    with pytest.raises(ValidationError):
        AudioRequest(session_id="", speaker="speaker_a", audio_path="clip.wav")


def test_translation_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        TranslationRequest(session_id="session", text="hello", source_language="fr")


def test_websocket_contract_is_versioned_and_discriminated() -> None:
    schema = ClientRoomEventAdapter.json_schema()
    assert schema["discriminator"]["propertyName"] == "type"
    assert PROTOCOL_VERSION in str(schema)


def test_websocket_contract_rejects_event_specific_payload_drift() -> None:
    with pytest.raises(ValidationError):
        ClientRoomEventAdapter.validate_python(
            {
                "protocol_version": PROTOCOL_VERSION,
                "type": "audio.start",
                "event_id": "event-1",
                "room_id": "room-1",
                "participant_id": "participant-1",
                "sequence": 1,
                "timestamp": "2026-07-19T00:00:00Z",
                "payload": {
                    "audio_format": "wav",
                    "sample_rate_hz": 44100,
                    "channels": 2,
                    "source_language": "vi",
                    "target_language": "en",
                },
            }
        )


def test_committed_websocket_contract_matches_models() -> None:
    path = Path("shared/contract/websocket-client-events.schema.json")
    assert json.loads(path.read_text(encoding="utf-8")) == ClientRoomEventAdapter.json_schema()
