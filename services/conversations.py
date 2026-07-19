import asyncio
import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared.schemas import (
    SaveConversationRequest,
    SavedConversationResponse,
)


class ConversationNotFoundError(LookupError):
    pass


class ConversationStore:
    """Small encrypted SQLite store for explicitly saved translated turns."""

    def __init__(self, database_path: Path, encryption_secret: str) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._cipher = AESGCM(hashlib.sha256(encryption_secret.encode("utf-8")).digest())
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS saved_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    owner_participant_id TEXT NOT NULL,
                    nonce BLOB NOT NULL,
                    encrypted_content BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    delete_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_saved_conversations_owner_created
                    ON saved_conversations(owner_participant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_saved_conversations_delete_at
                    ON saved_conversations(delete_at);
                """
            )

    async def save(
        self,
        room_id: str,
        owner_participant_id: str,
        request: SaveConversationRequest,
    ) -> SavedConversationResponse:
        return await asyncio.to_thread(self._save, room_id, owner_participant_id, request)

    def _save(
        self,
        room_id: str,
        owner_participant_id: str,
        request: SaveConversationRequest,
    ) -> SavedConversationResponse:
        now = datetime.now(UTC)
        delete_at = now + timedelta(hours=request.retention_hours)
        conversation_id = str(uuid4())
        content = {
            "turn_id": request.turn_id,
            "source_language": request.source_language,
            "target_language": request.target_language,
            "source_text": request.source_text,
            "translated_text": request.translated_text,
        }
        nonce = os.urandom(12)
        associated_data = f"{conversation_id}:{room_id}:{owner_participant_id}".encode()
        encrypted = self._cipher.encrypt(
            nonce,
            json.dumps(content, ensure_ascii=False).encode("utf-8"),
            associated_data,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO saved_conversations (
                    conversation_id, room_id, owner_participant_id, nonce,
                    encrypted_content, created_at, delete_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    room_id,
                    owner_participant_id,
                    nonce,
                    encrypted,
                    now.isoformat(),
                    delete_at.isoformat(),
                ),
            )
        return SavedConversationResponse(
            conversation_id=conversation_id,
            room_id=room_id,
            created_at=now,
            delete_at=delete_at,
            **content,
        )

    async def list_for_owner(
        self, room_id: str, owner_participant_id: str
    ) -> list[SavedConversationResponse]:
        return await asyncio.to_thread(self._list_for_owner, room_id, owner_participant_id)

    def _list_for_owner(
        self, room_id: str, owner_participant_id: str
    ) -> list[SavedConversationResponse]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM saved_conversations WHERE delete_at <= ?", (now,))
            rows = connection.execute(
                """
                SELECT * FROM saved_conversations
                WHERE room_id = ? AND owner_participant_id = ?
                ORDER BY created_at DESC
                """,
                (room_id, owner_participant_id),
            ).fetchall()
        return [self._decrypt(row) for row in rows]

    def _decrypt(self, row: sqlite3.Row) -> SavedConversationResponse:
        associated_data = (
            f"{row['conversation_id']}:{row['room_id']}:{row['owner_participant_id']}".encode()
        )
        plaintext = self._cipher.decrypt(
            row["nonce"], row["encrypted_content"], associated_data
        )
        content = json.loads(plaintext.decode("utf-8"))
        return SavedConversationResponse(
            conversation_id=row["conversation_id"],
            room_id=row["room_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            delete_at=datetime.fromisoformat(row["delete_at"]),
            **content,
        )

    async def delete(
        self, conversation_id: str, room_id: str, owner_participant_id: str
    ) -> None:
        deleted = await asyncio.to_thread(
            self._delete, conversation_id, room_id, owner_participant_id
        )
        if not deleted:
            raise ConversationNotFoundError(conversation_id)

    def _delete(self, conversation_id: str, room_id: str, owner_participant_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM saved_conversations
                WHERE conversation_id = ? AND room_id = ? AND owner_participant_id = ?
                """,
                (conversation_id, room_id, owner_participant_id),
            )
        return cursor.rowcount == 1
