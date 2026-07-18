from datetime import timedelta

from fastapi.testclient import TestClient

from apps.api.dependencies import get_room_manager, get_room_token_service
from apps.api.main import app
from services.room_tokens import RoomTokenService
from services.rooms import InMemoryRoomManager


def room_client() -> TestClient:
    manager = InMemoryRoomManager()
    tokens = RoomTokenService("test-secret-at-least-sixteen", timedelta(minutes=30))
    app.dependency_overrides[get_room_manager] = lambda: manager
    app.dependency_overrides[get_room_token_service] = lambda: tokens
    return TestClient(app)


def test_create_join_get_close_room_api() -> None:
    with room_client() as client:
        created = client.post(
            "/rooms",
            json={"display_name": "Phone A", "source_language": "vi", "target_language": "en"},
        )
        body = created.json()
        room_id = body["room_id"]
        token = body["access_token"]
        joined = client.post(
            "/rooms/join",
            json={
                "room_code": body["room_code"],
                "display_name": "Phone B",
                "source_language": "en",
                "target_language": "vi",
            },
        )
        state = client.get(
            f"/rooms/{room_id}", headers={"Authorization": f"Bearer {token}"}
        )
        unauthorized = client.get(
            f"/rooms/{room_id}", headers={"Authorization": "Bearer invalid"}
        )
        non_owner_close = client.delete(
            f"/rooms/{room_id}",
            headers={"Authorization": f"Bearer {joined.json()['access_token']}"},
        )
        closed = client.delete(
            f"/rooms/{room_id}", headers={"Authorization": f"Bearer {token}"}
        )
    app.dependency_overrides.clear()
    assert created.status_code == 201
    assert len(body["room_code"]) == 6
    assert body["status"] == "waiting"
    assert body["participant"]["display_name"] == "Phone A"
    assert body["expires_at"]
    assert joined.status_code == 200
    assert joined.json()["status"] == "ready"
    assert state.status_code == 200
    assert state.json()["participant_count"] == 2
    assert unauthorized.status_code == 401
    assert non_owner_close.status_code == 403
    assert non_owner_close.json()["detail"]["code"] == "ROOM_OWNER_REQUIRED"
    assert closed.status_code == 204


def test_room_api_validation_unknown_code_and_capacity() -> None:
    with room_client() as client:
        invalid_language = client.post(
            "/rooms",
            json={"display_name": "Phone", "source_language": "fr", "target_language": "en"},
        )
        unknown = client.post(
            "/rooms/join",
            json={
                "room_code": "ABC234",
                "display_name": "Phone",
                "source_language": "vi",
                "target_language": "en",
            },
        )
        created = client.post(
            "/rooms",
            json={"display_name": "A", "source_language": "vi", "target_language": "en"},
        ).json()
        join_body = {
            "room_code": created["room_code"],
            "display_name": "B",
            "source_language": "en",
            "target_language": "vi",
        }
        client.post("/rooms/join", json=join_body)
        full = client.post("/rooms/join", json={**join_body, "display_name": "C"})
    app.dependency_overrides.clear()
    assert invalid_language.status_code == 422
    assert unknown.status_code == 404
    assert full.status_code == 409
