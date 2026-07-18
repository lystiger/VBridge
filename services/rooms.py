import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from shared.logging import log_event
from shared.schemas import (
    InferenceMode,
    Language,
    RoomParticipant,
    RoomStateResponse,
    RoomStatus,
)

ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class RoomError(Exception):
    code = "INTERNAL_ERROR"


class RoomNotFoundError(RoomError):
    code = "ROOM_NOT_FOUND"


class InvalidRoomCodeError(RoomError):
    code = "INVALID_ROOM_CODE"


class RoomFullError(RoomError):
    code = "ROOM_FULL"


class RoomUnavailableError(RoomError):
    code = "ROOM_CLOSED"


class ParticipantNotFoundError(RoomError):
    code = "PARTICIPANT_NOT_FOUND"


class RoomPermissionError(RoomError):
    code = "ROOM_OWNER_REQUIRED"


class DuplicateEventError(RoomError):
    code = "DUPLICATE_EVENT"


class OutOfOrderEventError(RoomError):
    code = "OUT_OF_ORDER_EVENT"


@dataclass
class Participant:
    participant_id: str
    display_name: str
    source_language: Language
    target_language: Language
    joined_at: datetime
    is_owner: bool = False
    connected: bool = False
    last_seen_at: datetime | None = None
    websocket: Any | None = field(default=None, repr=False)


@dataclass
class Room:
    room_id: str
    room_code: str
    status: RoomStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    inference_mode: InferenceMode = "server"
    participants: dict[str, Participant] = field(default_factory=dict)
    processed_event_ids: set[str] = field(default_factory=set)
    last_sequence_by_participant: dict[str, int] = field(default_factory=dict)
    dispatch_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class InMemoryRoomManager:
    def __init__(self, ttl: timedelta = timedelta(minutes=30), max_participants: int = 2) -> None:
        self._rooms: dict[str, Room] = {}
        self._room_ids_by_code: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.ttl = ttl
        self.max_participants = max_participants

    async def create_room(
        self,
        display_name: str,
        source_language: Language,
        target_language: Language,
        inference_mode: InferenceMode = "server",
    ) -> tuple[Room, Participant]:
        now = datetime.now(UTC)
        async with self._lock:
            code = self._generate_code()
            participant = self._new_participant(
                display_name, source_language, target_language, now, is_owner=True
            )
            room = Room(
                room_id=str(uuid4()),
                room_code=code,
                status=RoomStatus.WAITING,
                created_at=now,
                updated_at=now,
                expires_at=now + self.ttl,
                inference_mode=inference_mode,
                participants={participant.participant_id: participant},
            )
            self._rooms[room.room_id] = room
            self._room_ids_by_code[code] = room.room_id
        log_event("room.created", room_id=room.room_id, room_code=room.room_code)
        return room, participant

    async def join_room(
        self,
        room_code: str,
        display_name: str,
        source_language: Language,
        target_language: Language,
    ) -> tuple[Room, Participant]:
        async with self._lock:
            room_id = self._room_ids_by_code.get(room_code.upper())
            if room_id is None:
                raise InvalidRoomCodeError(room_code)
            room = self._rooms[room_id]
            self._ensure_available(room)
            if len(room.participants) >= self.max_participants:
                raise RoomFullError(room_code)
            now = datetime.now(UTC)
            participant = self._new_participant(
                display_name, source_language, target_language, now
            )
            room.participants[participant.participant_id] = participant
            room.status = RoomStatus.READY
            self._touch(room, now)
        log_event("room.joined", room_id=room.room_id, participant_id=participant.participant_id)
        return room, participant

    async def get_room(self, room_id: str) -> Room:
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise RoomNotFoundError(room_id)
            return room

    async def connect(self, room_id: str, participant_id: str, websocket: Any) -> Room:
        async with self._lock:
            room = self._require_room(room_id)
            self._ensure_available(room)
            participant = self._require_participant(room, participant_id)
            previous = participant.websocket
            participant.websocket = websocket
            participant.connected = True
            participant.last_seen_at = datetime.now(UTC)
            everyone_connected = all(item.connected for item in room.participants.values())
            if everyone_connected and len(room.participants) == 2:
                room.status = RoomStatus.ACTIVE
            self._touch(room)
        if previous is not None and previous is not websocket:
            try:
                await previous.close(code=4007, reason="connection replaced")
            except RuntimeError:
                pass
        return room

    async def disconnect(self, room_id: str, participant_id: str, websocket: Any = None) -> Room:
        async with self._lock:
            room = self._require_room(room_id)
            participant = self._require_participant(room, participant_id)
            if websocket is not None and participant.websocket is not websocket:
                return room
            participant.websocket = None
            participant.connected = False
            participant.last_seen_at = datetime.now(UTC)
            if room.status not in {RoomStatus.CLOSED, RoomStatus.EXPIRED}:
                room.status = RoomStatus.WAITING
            self._touch(room)
            return room

    async def validate_event(
        self, room_id: str, participant_id: str, event_id: str, sequence: int
    ) -> Room:
        async with self._lock:
            room = self._require_room(room_id)
            self._ensure_available(room)
            self._require_participant(room, participant_id)
            if event_id in room.processed_event_ids:
                raise DuplicateEventError(event_id)
            previous = room.last_sequence_by_participant.get(participant_id, -1)
            if sequence <= previous:
                raise OutOfOrderEventError(str(sequence))
            if sequence > previous + 1:
                log_event(
                    "room.sequence_gap",
                    room_id=room_id,
                    participant_id=participant_id,
                    previous_sequence=previous,
                    sequence=sequence,
                )
            room.processed_event_ids.add(event_id)
            room.last_sequence_by_participant[participant_id] = sequence
            self._touch(room)
            return room

    async def broadcast(self, room_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            room = self._require_room(room_id)
            recipients = [item for item in room.participants.values() if item.connected]
        async with room.dispatch_lock:
            results = await asyncio.gather(
                *(self._send_safe(item, event) for item in recipients), return_exceptions=True
            )
        for participant, result in zip(recipients, results, strict=True):
            if isinstance(result, Exception):
                await self.disconnect(room_id, participant.participant_id, participant.websocket)

    async def close_room(self, room_id: str, participant_id: str) -> list[Any]:
        async with self._lock:
            room = self._require_room(room_id)
            participant = self._require_participant(room, participant_id)
            if not participant.is_owner:
                raise RoomPermissionError(participant_id)
            room.status = RoomStatus.CLOSED
            room.updated_at = datetime.now(UTC)
            self._room_ids_by_code.pop(room.room_code, None)
            sockets = [item.websocket for item in room.participants.values() if item.websocket]
        log_event("room.closed", room_id=room_id)
        return sockets

    async def expire_inactive_rooms(self, now: datetime | None = None) -> list[Room]:
        now = now or datetime.now(UTC)
        async with self._lock:
            expired = [
                room
                for room in self._rooms.values()
                if room.status not in {RoomStatus.CLOSED, RoomStatus.EXPIRED}
                and now >= room.expires_at
            ]
            for room in expired:
                room.status = RoomStatus.EXPIRED
                self._room_ids_by_code.pop(room.room_code, None)
        for room in expired:
            log_event("room.expired", room_id=room.room_id)
        return expired

    def state(self, room: Room) -> RoomStateResponse:
        return RoomStateResponse(
            room_id=room.room_id,
            room_code=room.room_code,
            status=room.status,
            inference_mode=room.inference_mode,
            participant_count=len(room.participants),
            participants=[self.participant_schema(item) for item in room.participants.values()],
            expires_at=room.expires_at,
        )

    @staticmethod
    def participant_schema(participant: Participant) -> RoomParticipant:
        return RoomParticipant(
            participant_id=participant.participant_id,
            display_name=participant.display_name,
            source_language=participant.source_language,
            target_language=participant.target_language,
            connected=participant.connected,
            is_owner=participant.is_owner,
        )

    async def counts(self) -> tuple[int, int]:
        async with self._lock:
            active = sum(
                room.status not in {RoomStatus.CLOSED, RoomStatus.EXPIRED}
                for room in self._rooms.values()
            )
            connected = sum(
                participant.connected
                for room in self._rooms.values()
                for participant in room.participants.values()
            )
            return active, connected

    def _generate_code(self) -> str:
        for _ in range(100):
            code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(6))
            if code not in self._room_ids_by_code:
                return code
        raise RuntimeError("could not reserve a unique room code")

    @staticmethod
    def _new_participant(
        display_name: str,
        source_language: Language,
        target_language: Language,
        now: datetime,
        is_owner: bool = False,
    ) -> Participant:
        return Participant(
            str(uuid4()), display_name, source_language, target_language, now, is_owner=is_owner
        )

    def _require_room(self, room_id: str) -> Room:
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomNotFoundError(room_id)
        return room

    @staticmethod
    def _require_participant(room: Room, participant_id: str) -> Participant:
        try:
            return room.participants[participant_id]
        except KeyError as exc:
            raise ParticipantNotFoundError(participant_id) from exc

    @staticmethod
    def _ensure_available(room: Room) -> None:
        if room.status in {RoomStatus.CLOSED, RoomStatus.EXPIRED}:
            error = RoomUnavailableError(room.room_id)
            error.code = "ROOM_EXPIRED" if room.status == RoomStatus.EXPIRED else "ROOM_CLOSED"
            raise error

    def _touch(self, room: Room, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        room.updated_at = now
        room.expires_at = now + self.ttl

    @staticmethod
    async def _send_safe(participant: Participant, event: dict[str, Any]) -> None:
        await participant.websocket.send_json(event)
