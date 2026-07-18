import asyncio
import struct
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from apps.api.dependencies import (
    get_metrics_collector,
    get_pipeline_service,
    get_room_manager,
    get_room_token_service,
)
from apps.api.main import app, settings
from services.asr import MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.room_tokens import RoomTokenService
from services.rooms import InMemoryRoomManager
from services.translation import MockTranslationService
from services.tts import MockTTSService
from shared.schemas import ASRResponse, AudioRequest


class SlowMockASRService(MockASRService):
    async def transcribe(self, request: AudioRequest) -> ASRResponse:
        await asyncio.sleep(0.05)
        return await super().transcribe(request)


def make_client(tmp_path: Path) -> TestClient:
    manager = InMemoryRoomManager()
    tokens = RoomTokenService("test-secret-at-least-sixteen", timedelta(minutes=30))
    collector = MetricsCollector()
    pipeline = PipelineService(
        SlowMockASRService(), MockTranslationService(), MockTTSService(tmp_path)
    )
    app.dependency_overrides[get_room_manager] = lambda: manager
    app.dependency_overrides[get_room_token_service] = lambda: tokens
    app.dependency_overrides[get_pipeline_service] = lambda: pipeline
    app.dependency_overrides[get_metrics_collector] = lambda: collector
    settings.vad_mode = "energy"
    return TestClient(app)


def envelope(
    event_type: str,
    event_id: str,
    room_id: str,
    participant_id: str,
    sequence: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "type": event_type,
        "event_id": event_id,
        "room_id": room_id,
        "participant_id": participant_id,
        "sequence": sequence,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }


def receive_until(socket, event_type: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
    for _ in range(12):
        event = socket.receive_json()
        if event["type"] == event_type:
            return event
    raise AssertionError(f"event {event_type} was not received")


def test_two_phones_receive_identical_translation_and_reconnect(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/rooms",
            json={"display_name": "Phone A", "source_language": "vi", "target_language": "en"},
        ).json()
        room_id = created["room_id"]
        first = created["participant"]
        with client.websocket_connect(
            f"/ws/rooms/{room_id}?token={created['access_token']}"
        ) as phone_a:
            assert phone_a.receive_json()["type"] == "room.state"
            joined = client.post(
                "/rooms/join",
                json={
                    "room_code": created["room_code"],
                    "display_name": "Phone B",
                    "source_language": "en",
                    "target_language": "vi",
                },
            ).json()
            assert receive_until(phone_a, "participant.joined")["participant_id"] == joined[
                "participant"
            ]["participant_id"]
            with client.websocket_connect(
                f"/ws/rooms/{room_id}?token={joined['access_token']}"
            ) as phone_b:
                assert phone_b.receive_json()["type"] == "room.state"
                receive_until(phone_a, "room.state")
                start = envelope(
                    "audio.start",
                    "audio-event-1",
                    room_id,
                    first["participant_id"],
                    1,
                    {
                        "audio_format": "pcm_s16le",
                        "sample_rate_hz": 16_000,
                        "channels": 1,
                        "source_language": "vi",
                        "target_language": "en",
                    },
                )
                phone_a.send_json(start)
                phone_a.send_bytes(struct.pack("<1600h", *([2000] * 1600)))
                phone_a.send_json(
                    envelope(
                        "audio.end",
                        "audio-end-1",
                        room_id,
                        first["participant_id"],
                        2,
                    )
                )
                assert phone_a.receive_json()["type"] == "audio.queued"
                phone_a.send_json(
                    envelope(
                        "ping",
                        "ping-1",
                        room_id,
                        first["participant_id"],
                        3,
                    )
                )
                assert phone_a.receive_json()["type"] == "pong"
                result_a = receive_until(phone_a, "translation.result")
                result_b = receive_until(phone_b, "translation.result")
                assert result_a == result_b
                assert result_a["event_id"] == "audio-event-1"
                assert result_a["sequence"] == 1
                assert result_a["participant_id"] == first["participant_id"]
                assert result_a["payload"]["source_text"].startswith("Xin ch")
                assert result_a["payload"]["translated_text"] == "Hello"

                phone_a.send_json(start)
                duplicate = receive_until(phone_a, "error")
                assert duplicate["payload"]["code"] == "DUPLICATE_EVENT"
        with client.websocket_connect(
            f"/ws/rooms/{room_id}?token={created['access_token']}"
        ) as reconnected:
            assert reconnected.receive_json()["type"] == "room.state"
    app.dependency_overrides.clear()


def test_invalid_token_and_malformed_event_are_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/rooms",
            json={"display_name": "A", "source_language": "vi", "target_language": "en"},
        ).json()
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect(f"/ws/rooms/{created['room_id']}?token=bad"):
                pass
        assert rejected.value.code == 4001
        with client.websocket_connect(
            f"/ws/rooms/{created['room_id']}?token={created['access_token']}"
        ) as socket:
            socket.receive_json()
            socket.send_text("not-json")
            error = socket.receive_json()
            assert error["type"] == "error"
            assert error["payload"]["code"] == "INVALID_EVENT"
    app.dependency_overrides.clear()
