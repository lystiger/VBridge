import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_session_manager
from apps.api.main import app
from services.asr import MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.sessions import SessionManager
from services.translation import MockTranslationService
from services.tts import MockTTSService


def make_manager(tmp_path: Path) -> SessionManager:
    pipeline = PipelineService(
        MockASRService(), MockTranslationService(), MockTTSService(tmp_path)
    )
    return SessionManager(pipeline, MetricsCollector(), tmp_path / "turns")


def receive_until(websocket, event_type: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
    for _ in range(10):
        event = websocket.receive_json()
        if event["type"] == event_type:
            return event
    raise AssertionError(f"did not receive {event_type}")


def test_session_rest_join_and_two_participant_limit(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app.dependency_overrides[get_session_manager] = lambda: manager
    with TestClient(app) as client:
        created = client.post("/sessions")
        session_id = created.json()["session_id"]
        first = client.post(
            f"/sessions/{session_id}/participants",
            json={"source_language": "vi", "target_language": "en"},
        )
        second = client.post(
            f"/sessions/{session_id}/participants",
            json={"source_language": "en", "target_language": "vi"},
        )
        full = client.post(
            f"/sessions/{session_id}/participants",
            json={"source_language": "vi", "target_language": "en"},
        )
    app.dependency_overrides.clear()
    assert created.status_code == 201
    assert first.status_code == second.status_code == 200
    assert full.status_code == 409


def test_websocket_broadcast_duplicate_and_reconnect(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app.dependency_overrides[get_session_manager] = lambda: manager
    with TestClient(app) as client:
        session_id = client.post("/sessions").json()["session_id"]
        first_id = client.post(
            f"/sessions/{session_id}/participants",
            json={"source_language": "vi", "target_language": "en"},
        ).json()["participant_id"]
        second_id = client.post(
            f"/sessions/{session_id}/participants",
            json={"source_language": "en", "target_language": "vi"},
        ).json()["participant_id"]
        with client.websocket_connect(
            f"/sessions/{session_id}/ws?participant_id={first_id}"
        ) as first:
            assert first.receive_json()["type"] == "session.ready"
            with client.websocket_connect(
                f"/sessions/{session_id}/ws?participant_id={second_id}"
            ) as second:
                assert second.receive_json()["type"] == "session.ready"
                assert first.receive_json()["type"] == "participant.connected"
                metadata = {
                    "type": "turn.start",
                    "sequence": 1,
                    "source_language": "vi",
                    "target_language": "en",
                }
                first.send_json(metadata)
                first.send_bytes(b"complete audio turn")
                translated = receive_until(second, "translation.final")
                assert translated["participant_id"] == first_id
                assert translated["sequence"] == 1
                assert translated["text"] == "Hello"
                receive_until(first, "turn.completed")

                first.send_json(metadata)
                first.send_bytes(b"retried audio turn")
                replay = receive_until(first, "translation.final")
                assert replay["duplicate"] is True
        with client.websocket_connect(
            f"/sessions/{session_id}/ws?participant_id={first_id}"
        ) as reconnected:
            ready = reconnected.receive_json()
            assert ready["type"] == "session.ready"
            assert ready["next_sequence"] == 2
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_out_of_order_turns_wait_for_missing_sequence(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    session = await manager.create_session()
    joined = await manager.join(session.session_id, "vi", "en")
    participant = session.participants[joined.participant_id]

    assert (
        await manager.submit_turn(
            session.session_id, joined.participant_id, 2, b"second", "vi", "en"
        )
        == "queued"
    )
    await asyncio.sleep(0)
    assert participant.next_sequence == 1
    assert 2 in participant.pending

    await manager.submit_turn(
        session.session_id, joined.participant_id, 1, b"first", "vi", "en"
    )
    for _ in range(20):
        if participant.next_sequence == 3:
            break
        await asyncio.sleep(0.01)
    assert participant.next_sequence == 3
    assert list(participant.completed) == [1, 2]
