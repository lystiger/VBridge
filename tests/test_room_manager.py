import re
from datetime import UTC, datetime, timedelta

import pytest

from services.room_tokens import ExpiredTokenError, InvalidTokenError, RoomTokenService
from services.rooms import (
    ROOM_CODE_ALPHABET,
    DuplicateEventError,
    InMemoryRoomManager,
    InvalidRoomCodeError,
    OutOfOrderEventError,
    RoomFullError,
)
from shared.schemas import RoomStatus


class FakeSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.closed = False

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)

    async def close(self, **_kwargs: object) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_room_lifecycle_capacity_connections_and_close() -> None:
    manager = InMemoryRoomManager()
    room, creator = await manager.create_room("Phone A", "vi", "en")
    assert room.status == RoomStatus.WAITING
    assert re.fullmatch(f"[{ROOM_CODE_ALPHABET}]{{6}}", room.room_code)
    assert creator.participant_id in room.participants

    joined_room, joiner = await manager.join_room(room.room_code.lower(), "Phone B", "en", "vi")
    assert joined_room.status == RoomStatus.READY
    with pytest.raises(RoomFullError):
        await manager.join_room(room.room_code, "Phone C", "vi", "en")
    with pytest.raises(InvalidRoomCodeError):
        await manager.join_room("AAAAAA", "Unknown", "vi", "en")

    old_socket = FakeSocket()
    replacement = FakeSocket()
    other_socket = FakeSocket()
    await manager.connect(room.room_id, creator.participant_id, old_socket)
    await manager.connect(room.room_id, creator.participant_id, replacement)
    assert old_socket.closed
    await manager.connect(room.room_id, joiner.participant_id, other_socket)
    assert room.status == RoomStatus.ACTIVE
    await manager.disconnect(room.room_id, creator.participant_id, replacement)
    assert not creator.connected
    assert room.status == RoomStatus.WAITING

    sockets = await manager.close_room(room.room_id)
    assert room.status == RoomStatus.CLOSED
    assert sockets == [other_socket]
    with pytest.raises(InvalidRoomCodeError):
        await manager.join_room(room.room_code, "Late", "vi", "en")


@pytest.mark.asyncio
async def test_event_validation_deduplicates_and_accepts_sequence_gaps() -> None:
    manager = InMemoryRoomManager()
    room, participant = await manager.create_room("Phone A", "vi", "en")
    await manager.validate_event(room.room_id, participant.participant_id, "event-1", 1)
    with pytest.raises(DuplicateEventError):
        await manager.validate_event(room.room_id, participant.participant_id, "event-1", 2)
    with pytest.raises(OutOfOrderEventError):
        await manager.validate_event(room.room_id, participant.participant_id, "event-2", 1)
    await manager.validate_event(room.room_id, participant.participant_id, "event-3", 4)
    assert room.last_sequence_by_participant[participant.participant_id] == 4


@pytest.mark.asyncio
async def test_room_codes_are_unique_and_inactive_rooms_expire() -> None:
    manager = InMemoryRoomManager(ttl=timedelta(seconds=1))
    first, _ = await manager.create_room("A", "vi", "en")
    second, _ = await manager.create_room("B", "en", "vi")
    assert first.room_id != second.room_id
    assert first.room_code != second.room_code
    expired = await manager.expire_inactive_rooms(datetime.now(UTC) + timedelta(seconds=2))
    assert {room.room_id for room in expired} == {first.room_id, second.room_id}
    assert all(room.status == RoomStatus.EXPIRED for room in expired)


def test_room_token_is_signed_bound_and_expiring() -> None:
    service = RoomTokenService("test-secret-at-least-sixteen", timedelta(minutes=5))
    now = datetime(2026, 7, 18, tzinfo=UTC)
    token = service.issue("room", "participant", now)
    claims = service.verify(token, now + timedelta(minutes=1))
    assert claims["room_id"] == "room"
    assert claims["participant_id"] == "participant"
    with pytest.raises(InvalidTokenError):
        service.verify(token + "tampered", now)
    with pytest.raises(ExpiredTokenError):
        service.verify(token, now + timedelta(minutes=6))
