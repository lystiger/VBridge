import sqlite3
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_conversation_store,
    get_metrics_collector,
    get_room_manager,
    get_room_token_service,
)
from apps.api.main import app
from services.conversations import ConversationStore
from services.metrics import MetricsCollector
from services.room_tokens import RoomTokenService
from services.rooms import InMemoryRoomManager


def test_opt_in_encrypted_conversation_lifecycle_and_owner_isolation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "conversations.db"
    store = ConversationStore(database_path, "test-conversation-encryption-secret")
    manager = InMemoryRoomManager()
    tokens = RoomTokenService("test-room-secret-at-least-sixteen", timedelta(minutes=30))
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_room_manager] = lambda: manager
    app.dependency_overrides[get_room_token_service] = lambda: tokens
    app.dependency_overrides[get_metrics_collector] = MetricsCollector

    try:
        with TestClient(app) as client:
            owner = client.post(
                "/rooms",
                json={
                    "display_name": "Owner",
                    "source_language": "vi",
                    "target_language": "en",
                },
            ).json()
            room_id = owner["room_id"]
            owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
            peer = client.post(
                "/rooms/join",
                json={
                    "room_code": owner["room_code"],
                    "display_name": "Peer",
                    "source_language": "en",
                    "target_language": "vi",
                },
            ).json()
            peer_headers = {"Authorization": f"Bearer {peer['access_token']}"}

            payload = {
                "consent": True,
                "turn_id": "turn-1",
                "source_language": "vi",
                "target_language": "en",
                "source_text": "Nội dung riêng tư",
                "translated_text": "Private content",
                "retention_hours": 24,
            }
            no_consent = client.post(
                f"/rooms/{room_id}/conversations",
                headers=owner_headers,
                json={**payload, "consent": False},
            )
            assert no_consent.status_code == 422

            saved = client.post(
                f"/rooms/{room_id}/conversations",
                headers=owner_headers,
                json=payload,
            )
            assert saved.status_code == 201
            conversation = saved.json()
            assert conversation["translated_text"] == "Private content"

            raw_database = database_path.read_bytes()
            assert b"Private content" not in raw_database
            assert "Nội dung riêng tư".encode() not in raw_database

            # A fresh repository instance proves persistence across application instances.
            restarted_store = ConversationStore(
                database_path, "test-conversation-encryption-secret"
            )
            app.dependency_overrides[get_conversation_store] = lambda: restarted_store
            owner_list = client.get(
                f"/rooms/{room_id}/conversations", headers=owner_headers
            )
            assert owner_list.status_code == 200
            assert owner_list.json()["conversations"] == [conversation]

            peer_list = client.get(
                f"/rooms/{room_id}/conversations", headers=peer_headers
            )
            assert peer_list.json()["conversations"] == []
            peer_delete = client.delete(
                f"/rooms/{room_id}/conversations/{conversation['conversation_id']}",
                headers=peer_headers,
            )
            assert peer_delete.status_code == 404

            expiring = client.post(
                f"/rooms/{room_id}/conversations",
                headers=owner_headers,
                json={**payload, "turn_id": "turn-expiring"},
            ).json()
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "UPDATE saved_conversations SET delete_at = ? WHERE conversation_id = ?",
                    ("2000-01-01T00:00:00+00:00", expiring["conversation_id"]),
                )
            after_retention_cleanup = client.get(
                f"/rooms/{room_id}/conversations", headers=owner_headers
            ).json()["conversations"]
            assert [item["conversation_id"] for item in after_retention_cleanup] == [
                conversation["conversation_id"]
            ]

            deleted = client.delete(
                f"/rooms/{room_id}/conversations/{conversation['conversation_id']}",
                headers=owner_headers,
            )
            assert deleted.status_code == 204
            assert client.get(
                f"/rooms/{room_id}/conversations", headers=owner_headers
            ).json()["conversations"] == []

        with sqlite3.connect(database_path) as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM saved_conversations"
            ).fetchone()[0]
        assert remaining == 0
    finally:
        app.dependency_overrides.clear()
