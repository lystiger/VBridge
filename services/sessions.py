import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import WebSocket

from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from shared.logging import log_event
from shared.schemas import AudioRequest, Language, ParticipantResponse


class SessionNotFoundError(KeyError):
    pass


class ParticipantNotFoundError(KeyError):
    pass


class InvalidSequenceError(ValueError):
    pass


@dataclass
class PendingTurn:
    sequence: int
    audio: bytes
    source_language: Language
    target_language: Language
    received_at: float = field(default_factory=perf_counter)


@dataclass
class ParticipantState:
    participant_id: str
    source_language: Language
    target_language: Language
    websocket: WebSocket | None = None
    next_sequence: int = 1
    pending: dict[int, PendingTurn] = field(default_factory=dict)
    completed: dict[int, list[dict[str, object]]] = field(default_factory=dict)
    worker: asyncio.Task[None] | None = None


@dataclass
class SessionState:
    session_id: str
    participants: dict[str, ParticipantState] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    dispatch_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Process-local session state for the two-phone conversation protocol."""

    def __init__(
        self,
        pipeline: PipelineService,
        metrics: MetricsCollector,
        audio_dir: Path,
        max_participants: int = 2,
    ) -> None:
        self.pipeline = pipeline
        self.metrics = metrics
        self.audio_dir = audio_dir
        self.max_participants = max_participants
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> SessionState:
        session = SessionState(session_id=str(uuid4()))
        async with self._lock:
            self._sessions[session.session_id] = session
        log_event("session_created", session_id=session.session_id)
        return session

    def get_session(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(session_id) from exc

    async def join(
        self,
        session_id: str,
        source_language: Language,
        target_language: Language,
        participant_id: str | None = None,
    ) -> ParticipantResponse:
        session = self.get_session(session_id)
        async with session.lock:
            if participant_id and participant_id in session.participants:
                participant = session.participants[participant_id]
                participant.source_language = source_language
                participant.target_language = target_language
            else:
                if len(session.participants) >= self.max_participants:
                    raise ValueError("session already has two participants")
                participant_id = participant_id or str(uuid4())
                participant = ParticipantState(participant_id, source_language, target_language)
                session.participants[participant_id] = participant
        log_event("participant_joined", session_id=session_id, participant_id=participant_id)
        return self._participant_response(session_id, participant)

    async def connect(
        self, session_id: str, participant_id: str, websocket: WebSocket
    ) -> ParticipantState:
        session = self.get_session(session_id)
        async with session.lock:
            participant = self._get_participant(session, participant_id)
            previous = participant.websocket
            participant.websocket = websocket
        if previous is not None and previous is not websocket:
            await previous.close(code=4001, reason="participant reconnected")
        await websocket.send_json(
            {
                "type": "session.ready",
                **self._participant_response(session_id, participant).model_dump(),
                "next_sequence": participant.next_sequence,
            }
        )
        await self.broadcast(
            session,
            {
                "type": "participant.connected",
                "session_id": session_id,
                "participant_id": participant_id,
            },
            exclude=participant_id,
        )
        return participant

    async def disconnect(self, session_id: str, participant_id: str, websocket: WebSocket) -> None:
        try:
            session = self.get_session(session_id)
        except SessionNotFoundError:
            return
        async with session.lock:
            participant = self._get_participant(session, participant_id)
            if participant.websocket is not websocket:
                return
            participant.websocket = None
        log_event("participant_disconnected", session_id=session_id, participant_id=participant_id)
        await self.broadcast(
            session,
            {
                "type": "participant.disconnected",
                "session_id": session_id,
                "participant_id": participant_id,
            },
        )

    async def submit_turn(
        self,
        session_id: str,
        participant_id: str,
        sequence: int,
        audio: bytes,
        source_language: Language,
        target_language: Language,
    ) -> str:
        if sequence < 1:
            raise InvalidSequenceError("sequence must be at least 1")
        if not audio:
            raise ValueError("audio payload is empty")
        session = self.get_session(session_id)
        async with session.lock:
            participant = self._get_participant(session, participant_id)
            if (events := participant.completed.get(sequence)) is not None:
                websocket = participant.websocket
                if websocket is not None:
                    for event in events:
                        await websocket.send_json({**event, "duplicate": True})
                return "completed_duplicate"
            if sequence < participant.next_sequence or sequence in participant.pending:
                return "duplicate"
            participant.pending[sequence] = PendingTurn(
                sequence, audio, source_language, target_language
            )
            if participant.worker is None or participant.worker.done():
                participant.worker = asyncio.create_task(
                    self._drain(session, participant),
                    name=f"session-{session_id}-{participant_id}",
                )
        return "queued"

    async def broadcast(
        self,
        session: SessionState,
        event: dict[str, object],
        exclude: str | None = None,
    ) -> float:
        started = perf_counter()
        async with session.dispatch_lock:
            recipients = [
                participant.websocket
                for participant in session.participants.values()
                if participant.participant_id != exclude and participant.websocket is not None
            ]
            for websocket in recipients:
                try:
                    await websocket.send_json(event)
                except RuntimeError:
                    pass
        return (perf_counter() - started) * 1000

    async def _drain(self, session: SessionState, participant: ParticipantState) -> None:
        while True:
            async with session.lock:
                turn = participant.pending.pop(participant.next_sequence, None)
                if turn is None:
                    participant.worker = None
            if turn is None:
                return
            await self._process_turn(session, participant, turn)
            async with session.lock:
                participant.next_sequence += 1

    async def _process_turn(
        self, session: SessionState, participant: ParticipantState, turn: PendingTurn
    ) -> None:
        queue_ms = (perf_counter() - turn.received_at) * 1000
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{session.session_id}-{participant.participant_id}-{turn.sequence}.audio"
        path = self.audio_dir / filename
        path.write_bytes(turn.audio)
        result = await self.pipeline.process(
            AudioRequest(
                session_id=session.session_id,
                speaker=participant.participant_id,
                language=turn.source_language,
                audio_path=str(path),
            ),
            target_language=turn.target_language,
        )
        base: dict[str, object] = {
            "session_id": session.session_id,
            "participant_id": participant.participant_id,
            "sequence": turn.sequence,
            "source_language": result.source_language,
            "target_language": result.target_language,
        }
        events = [
            {"type": "transcript.final", **base, "text": result.transcript},
            {
                "type": "translation.final",
                **base,
                "text": result.translation,
                "audio_url": result.audio_url,
                "asr_ms": result.asr_ms,
                "mt_ms": result.translation_ms,
            },
        ]
        dispatch_ms = 0.0
        for event in events:
            dispatch_ms += await self.broadcast(session, event)
        end_to_end_ms = (perf_counter() - turn.received_at) * 1000
        completed = {
            "type": "turn.completed",
            **base,
            "queue_ms": queue_ms,
            "dispatch_ms": dispatch_ms,
            "end_to_end_ms": end_to_end_ms,
        }
        dispatch_ms += await self.broadcast(session, completed)
        events.append(completed)
        participant.completed[turn.sequence] = events
        await self.metrics.record_session_turn(result, queue_ms, dispatch_ms, end_to_end_ms)
        log_event(
            "session_turn_completed",
            **base,
            queue_ms=queue_ms,
            dispatch_ms=dispatch_ms,
            end_to_end_ms=end_to_end_ms,
        )

    @staticmethod
    def _get_participant(session: SessionState, participant_id: str) -> ParticipantState:
        try:
            return session.participants[participant_id]
        except KeyError as exc:
            raise ParticipantNotFoundError(participant_id) from exc

    @staticmethod
    def _participant_response(
        session_id: str, participant: ParticipantState
    ) -> ParticipantResponse:
        return ParticipantResponse(
            session_id=session_id,
            participant_id=participant.participant_id,
            source_language=participant.source_language,
            target_language=participant.target_language,
            connected=participant.websocket is not None,
        )
