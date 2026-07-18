import asyncio
import wave
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from apps.api.dependencies import (
    get_metrics_collector,
    get_pipeline_service,
    get_room_manager,
    get_room_token_service,
    get_session_manager,
)
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.room_tokens import ExpiredTokenError, InvalidTokenError, RoomTokenService
from services.rooms import (
    DuplicateEventError,
    InMemoryRoomManager,
    InvalidRoomCodeError,
    OutOfOrderEventError,
    Participant,
    ParticipantNotFoundError,
    Room,
    RoomFullError,
    RoomNotFoundError,
    RoomPermissionError,
    RoomUnavailableError,
)
from services.sessions import (
    ParticipantNotFoundError as SessionParticipantNotFoundError,
)
from services.sessions import (
    SessionManager,
    SessionNotFoundError,
)
from services.streaming import StreamingPipelineService
from services.vad import EnergyVAD, SileroVAD
from shared.config import get_settings
from shared.logging import configure_logging, log_event
from shared.schemas import (
    PROTOCOL_VERSION,
    ASRResponse,
    AudioRequest,
    ClientRoomEventAdapter,
    CreateRoomRequest,
    HealthResponse,
    JoinRoomRequest,
    MetricsResponse,
    ParticipantJoinRequest,
    ParticipantResponse,
    PipelineResponse,
    RoomAccessResponse,
    RoomStateResponse,
    SessionCreateResponse,
    TranslationRequest,
    TranslationResponse,
    TTSRequest,
    TTSResponse,
    TurnStartRequest,
)

settings = get_settings()
settings.audio_output_dir.mkdir(parents=True, exist_ok=True)
configure_logging()


async def refresh_room_gauges(
    manager: InMemoryRoomManager, collector: MetricsCollector
) -> None:
    active, connected = await manager.counts()
    await collector.set_room_gauges(active, connected)


async def cleanup_rooms(stop: asyncio.Event) -> None:
    manager = get_room_manager()
    collector = get_metrics_collector()
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.room_cleanup_interval_seconds)
            continue
        except TimeoutError:
            pass
        expired = await manager.expire_inactive_rooms()
        for room in expired:
            await collector.increment_room("rooms_expired_total")
            for participant in room.participants.values():
                if participant.websocket is not None:
                    try:
                        await participant.websocket.close(code=4005, reason="room expired")
                    except RuntimeError:
                        pass
        await refresh_room_gauges(manager, collector)


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    stop = asyncio.Event()
    cleanup_task = asyncio.create_task(cleanup_rooms(stop), name="room-cleanup")
    try:
        yield
    finally:
        stop.set()
        await cleanup_task


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=settings.audio_output_dir), name="audio")


@app.get("/contract/websocket.schema.json", include_in_schema=False)
async def websocket_contract() -> JSONResponse:
    """Machine-readable client-to-server WebSocket contract."""

    return JSONResponse(ClientRoomEventAdapter.json_schema())

WS_INVALID_TOKEN = 4001
WS_ROOM_NOT_FOUND = 4002
WS_ROOM_CLOSED = 4004
WS_PARTICIPANT_NOT_FOUND = 4006
WS_PROTOCOL_VIOLATION = 4007


def event_envelope(
    event_type: str,
    room_id: str,
    participant_id: str = "system",
    sequence: int = 0,
    payload: dict[str, object] | None = None,
    event_id: str | None = None,
) -> dict[str, object]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": event_type,
        "event_id": event_id or str(uuid4()),
        "room_id": room_id,
        "participant_id": participant_id,
        "sequence": sequence,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }


def error_event(
    room_id: str, code: str, message: str, sequence: int = 0, retryable: bool = False
) -> dict[str, object]:
    return event_envelope(
        "error",
        room_id,
        sequence=sequence,
        payload={"code": code, "message": message, "retryable": retryable},
    )


@app.post("/sessions", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> SessionCreateResponse:
    session = await manager.create_session()
    return SessionCreateResponse(session_id=session.session_id)


@app.post("/sessions/{session_id}/participants", response_model=ParticipantResponse)
async def join_session(
    session_id: str,
    request: ParticipantJoinRequest,
    manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> ParticipantResponse:
    try:
        return await manager.join(
            session_id,
            request.source_language,
            request.target_language,
            request.participant_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.websocket("/sessions/{session_id}/ws")
async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> None:
    participant_id = websocket.query_params.get("participant_id", "")
    await websocket.accept()
    try:
        participant = await manager.connect(session_id, participant_id, websocket)
    except (SessionNotFoundError, SessionParticipantNotFoundError):
        await websocket.send_json({"type": "error", "code": "not_found"})
        await websocket.close(code=4404)
        return
    try:
        while True:
            try:
                metadata = TurnStartRequest.model_validate(await websocket.receive_json())
                audio = await websocket.receive_bytes()
                status = await manager.submit_turn(
                    session_id,
                    participant.participant_id,
                    metadata.sequence,
                    audio,
                    metadata.source_language,
                    metadata.target_language,
                )
                await websocket.send_json(
                    {
                        "type": "turn.accepted",
                        "session_id": session_id,
                        "participant_id": participant.participant_id,
                        "sequence": metadata.sequence,
                        "status": status,
                    }
                )
            except (ValidationError, ValueError) as exc:
                await websocket.send_json(
                    {"type": "error", "code": "invalid_turn", "detail": str(exc)}
                )
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(session_id, participant.participant_id, websocket)


def room_access_response(
    manager: InMemoryRoomManager,
    token_service: RoomTokenService,
    room: Room,
    participant: Participant,
) -> RoomAccessResponse:
    return RoomAccessResponse(
        room_id=room.room_id,
        room_code=room.room_code,
        status=room.status,
        inference_mode=room.inference_mode,
        participant=manager.participant_schema(participant),
        access_token=token_service.issue(room.room_id, participant.participant_id),
        expires_at=room.expires_at,
    )


def verify_bearer(
    authorization: str | None, token_service: RoomTokenService, room_id: str
) -> dict[str, str | int]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
    try:
        claims = token_service.verify(authorization.removeprefix("Bearer "))
    except ExpiredTokenError as exc:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED"}) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc
    if claims["room_id"] != room_id:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
    return claims


@app.post("/rooms", response_model=RoomAccessResponse, status_code=201)
async def create_room(
    request: CreateRoomRequest,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
) -> RoomAccessResponse:
    room, participant = await manager.create_room(
        request.display_name,
        request.source_language,
        request.target_language,
        request.inference_mode,
    )
    await collector.increment_room("rooms_created_total")
    await refresh_room_gauges(manager, collector)
    return room_access_response(manager, token_service, room, participant)


@app.post("/rooms/join", response_model=RoomAccessResponse)
async def join_room(
    request: JoinRoomRequest,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
) -> RoomAccessResponse:
    try:
        room, participant = await manager.join_room(
            request.room_code,
            request.display_name,
            request.source_language,
            request.target_language,
        )
    except InvalidRoomCodeError as exc:
        await collector.increment_room("room_join_failures_total")
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    except RoomFullError as exc:
        await collector.increment_room("room_join_failures_total")
        raise HTTPException(status_code=409, detail={"code": exc.code}) from exc
    except RoomUnavailableError as exc:
        await collector.increment_room("room_join_failures_total")
        status_code = 410 if exc.code == "ROOM_EXPIRED" else 409
        raise HTTPException(status_code=status_code, detail={"code": exc.code}) from exc
    await manager.broadcast(
        room.room_id,
        event_envelope(
            "participant.joined",
            room.room_id,
            participant.participant_id,
            payload={"display_name": participant.display_name},
        ),
    )
    await collector.increment_room("rooms_joined_total")
    await refresh_room_gauges(manager, collector)
    return room_access_response(manager, token_service, room, participant)


@app.get("/rooms/{room_id}", response_model=RoomStateResponse)
async def get_room_state(
    room_id: str,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> RoomStateResponse:
    claims = verify_bearer(authorization, token_service, room_id)
    try:
        room = await manager.get_room(room_id)
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    if claims["participant_id"] not in room.participants:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
    return manager.state(room)


@app.delete("/rooms/{room_id}", status_code=204)
async def close_room(
    room_id: str,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    claims = verify_bearer(authorization, token_service, room_id)
    room = await manager.get_room(room_id)
    if claims["participant_id"] not in room.participants:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
    try:
        sockets = await manager.close_room(room_id, str(claims["participant_id"]))
    except RoomPermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": exc.code}) from exc
    await collector.increment_room("rooms_closed_total")
    await refresh_room_gauges(manager, collector)
    event = event_envelope("room.closed", room_id)
    for websocket in sockets:
        try:
            await websocket.send_json(event)
            await websocket.close(code=4004, reason="room closed")
        except RuntimeError:
            pass


def wav_duration_ms(path: str) -> float | None:
    try:
        with wave.open(path, "rb") as audio:
            return audio.getnframes() / audio.getframerate() * 1000
    except (OSError, EOFError, wave.Error):
        return None


@app.websocket("/ws/rooms/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
    pipeline: Annotated[PipelineService, Depends(get_pipeline_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
) -> None:
    token = websocket.query_params.get("token", "")
    try:
        claims = token_service.verify(token)
        if claims["room_id"] != room_id:
            raise InvalidTokenError("token is scoped to another room")
        participant_id = str(claims["participant_id"])
        room = await manager.get_room(room_id)
        if participant_id not in room.participants:
            raise ParticipantNotFoundError(participant_id)
    except (InvalidTokenError, ExpiredTokenError):
        await websocket.close(code=WS_INVALID_TOKEN, reason="invalid or expired token")
        return
    except RoomNotFoundError:
        await websocket.close(code=WS_ROOM_NOT_FOUND, reason="room not found")
        return
    except ParticipantNotFoundError:
        await websocket.close(code=WS_PARTICIPANT_NOT_FOUND, reason="participant not found")
        return

    await websocket.accept()
    try:
        room = await manager.connect(room_id, participant_id, websocket)
    except RoomUnavailableError:
        await websocket.close(code=WS_ROOM_CLOSED, reason="room unavailable")
        return
    inference_mode = room.inference_mode
    await collector.increment_room("room_websocket_connections_total")
    await refresh_room_gauges(manager, collector)
    await manager.broadcast(
        room_id,
        event_envelope("room.state", room_id, payload=manager.state(room).model_dump(mode="json")),
    )
    active_turn: dict[str, object] | None = None
    turn_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
    turn_worker: asyncio.Task[None] | None = None
    # Server-hosted rooms (Scenario 2) run inference here; device rooms (Scenario 1)
    # only relay results the phones produce on-device, so no inference worker is needed.
    if inference_mode == "server":
        turn_worker = asyncio.create_task(
            room_turn_worker(
                turn_queue, websocket, manager, pipeline, collector, room_id, participant_id
            ),
            name=f"room-turns-{room_id}-{participant_id}",
        )
        turn_worker.add_done_callback(report_background_failure)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if (audio := message.get("bytes")) is not None:
                if inference_mode == "device":
                    await websocket.send_json(
                        error_event(
                            room_id, "INVALID_EVENT", "server does not accept audio in relay mode"
                        )
                    )
                    continue
                if active_turn is None:
                    await websocket.send_json(
                        error_event(room_id, "INVALID_EVENT", "binary audio requires audio.start")
                    )
                    continue
                buffer = active_turn["audio"]
                assert isinstance(buffer, bytearray)
                if len(buffer) + len(audio) > settings.room_max_audio_bytes:
                    active_turn = None
                    await websocket.send_json(
                        error_event(room_id, "INVALID_AUDIO_FORMAT", "audio turn is too large")
                    )
                    continue
                buffer.extend(audio)
                continue
            raw_event = message.get("text")
            if raw_event is None:
                continue
            if len(raw_event.encode()) > settings.room_max_json_bytes:
                await websocket.send_json(
                    error_event(room_id, "INVALID_EVENT", "event exceeds JSON size limit")
                )
                continue
            try:
                event = ClientRoomEventAdapter.validate_json(raw_event)
                await collector.increment_room("room_events_received_total")
                if event.room_id != room_id or event.participant_id != participant_id:
                    raise ValueError("event identity does not match authenticated participant")
                allowed_events = (
                    {"participant.ready", "translation.result", "ping"}
                    if inference_mode == "device"
                    else {"participant.ready", "audio.start", "audio.end", "ping"}
                )
                if event.type not in allowed_events:
                    raise ValueError("unsupported event type")
                if event.type == "audio.start":
                    if active_turn is not None:
                        raise ValueError("an audio turn is already active")
                if event.type == "audio.end" and active_turn is None:
                    raise ValueError("audio.end requires audio.start")
                await manager.validate_event(
                    room_id, participant_id, event.event_id, event.sequence
                )
                if event.type == "participant.ready":
                    await manager.broadcast(
                        room_id,
                        event_envelope(
                            "room.state",
                            room_id,
                            payload=manager.state(await manager.get_room(room_id)).model_dump(
                                mode="json"
                            ),
                        ),
                    )
                elif event.type == "ping":
                    await websocket.send_json(
                        event_envelope("pong", room_id, participant_id, event.sequence)
                    )
                elif event.type == "translation.result":
                    payload = event.payload.model_dump(exclude_none=True)
                    result_payload: dict[str, object] = {
                        "speaker_id": participant_id,
                        "source_language": payload["source_language"],
                        "target_language": payload["target_language"],
                        "source_text": payload["source_text"],
                        "translated_text": payload["translated_text"],
                        "inference_mode": "device",
                    }
                    for key in (
                        "asr_latency_ms",
                        "mt_latency_ms",
                        "end_to_end_latency_ms",
                        "audio_duration_ms",
                    ):
                        value = payload.get(key)
                        if isinstance(value, int | float):
                            result_payload[key] = float(value)
                    await manager.broadcast(
                        room_id,
                        event_envelope(
                            "translation.result",
                            room_id,
                            participant_id,
                            event.sequence,
                            event_id=event.event_id,
                            payload=result_payload,
                        ),
                    )
                    await collector.increment_room("room_device_results_total")
                elif event.type == "audio.start":
                    payload = event.payload.model_dump()
                    active_turn = {
                        "event_id": event.event_id,
                        "sequence": event.sequence,
                        "source_language": payload["source_language"],
                        "target_language": payload["target_language"],
                        "audio": bytearray(),
                    }
                elif event.type == "audio.end":
                    assert active_turn is not None
                    if turn_queue.qsize() >= settings.room_max_queued_turns:
                        await websocket.send_json(
                            error_event(
                                room_id,
                                "RATE_LIMITED",
                                "too many audio turns are queued",
                                retryable=True,
                            )
                        )
                    else:
                        active_turn["queued_at"] = perf_counter()
                        turn_queue.put_nowait(active_turn)
                        await websocket.send_json(
                            event_envelope(
                                "audio.queued",
                                room_id,
                                participant_id,
                                int(active_turn["sequence"]),
                                event_id=str(active_turn["event_id"]),
                            )
                        )
                    active_turn = None
            except (ValidationError, ValueError) as exc:
                await collector.increment_room("room_events_rejected_total")
                await websocket.send_json(
                    error_event(room_id, "INVALID_EVENT", str(exc), retryable=False)
                )
            except (DuplicateEventError, OutOfOrderEventError) as exc:
                await collector.increment_room("room_events_rejected_total")
                await websocket.send_json(
                    error_event(room_id, exc.code, str(exc), retryable=False)
                )
    except WebSocketDisconnect:
        pass
    finally:
        if turn_worker is not None:
            turn_queue.put_nowait(None)
        await manager.disconnect(room_id, participant_id, websocket)
        await collector.increment_room("room_websocket_disconnects_total")
        await refresh_room_gauges(manager, collector)
        await manager.broadcast(
            room_id,
            event_envelope(
                "participant.disconnected",
                room_id,
                participant_id,
                payload={"reconnect_grace_seconds": settings.room_reconnect_grace_seconds},
            ),
        )



def report_background_failure(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log_event("room.turn_worker_failed", error_type=type(exc).__name__)


async def room_turn_worker(
    queue: asyncio.Queue[dict[str, object] | None],
    websocket: WebSocket,
    manager: InMemoryRoomManager,
    pipeline: PipelineService,
    collector: MetricsCollector,
    room_id: str,
    participant_id: str,
) -> None:
    while True:
        turn = await queue.get()
        try:
            if turn is None:
                return
            await process_room_turn(
                websocket, manager, pipeline, collector, room_id, participant_id, turn
            )
        finally:
            queue.task_done()


async def process_room_turn(
    websocket: WebSocket,
    manager: InMemoryRoomManager,
    pipeline: PipelineService,
    collector: MetricsCollector,
    room_id: str,
    participant_id: str,
    turn: dict[str, object],
) -> None:
    audio = bytes(turn["audio"])
    started = float(turn.get("queued_at", perf_counter()))
    queue_ms = (perf_counter() - started) * 1000
    duration_ms = len(audio) / 2 / 16_000 * 1000
    if not audio or duration_ms > settings.room_max_turn_seconds * 1000:
        try:
            await websocket.send_json(
                error_event(room_id, "INVALID_AUDIO_FORMAT", "invalid audio duration")
            )
        except RuntimeError:
            pass
        return
    vad = (
        SileroVAD(settings.vad_threshold, settings.vad_min_silence_ms)
        if settings.vad_mode == "silero"
        else EnergyVAD()
    )
    service = StreamingPipelineService(
        pipeline,
        settings.audio_output_dir / "room-streams",
        vad,
        metrics=collector,
    )
    try:
        result, audio_duration_ms = await service.process_turn(
            audio,
            room_id,
            participant_id,
            turn["source_language"],  # type: ignore[arg-type]
            turn["target_language"],  # type: ignore[arg-type]
        )
    except Exception as exc:
        log_event(
            "room.pipeline_failed",
            room_id=room_id,
            participant_id=participant_id,
            event_id=turn["event_id"],
            sequence=turn["sequence"],
            error_type=type(exc).__name__,
        )
        try:
            await websocket.send_json(
                error_event(room_id, "PIPELINE_FAILURE", "inference failed", retryable=True)
            )
        except RuntimeError:
            pass
        await collector.increment_room("room_pipeline_failures_total")
        return
    end_to_end_ms = (perf_counter() - started) * 1000
    event = event_envelope(
        "translation.result",
        room_id,
        participant_id,
        int(turn["sequence"]),
        event_id=str(turn["event_id"]),
        payload={
            "speaker_id": participant_id,
            "source_language": result.source_language,
            "target_language": result.target_language,
            "source_text": result.transcript,
            "translated_text": result.translation,
            "inference_mode": "server",
            "audio_duration_ms": audio_duration_ms,
            "queue_latency_ms": queue_ms,
            "asr_latency_ms": result.asr_ms,
            "mt_latency_ms": result.translation_ms,
            "dispatch_latency_ms": 0.0,
            "end_to_end_latency_ms": end_to_end_ms,
            "model_versions": {
                "asr": collector.asr_model,
                "mt": collector.mt_model,
            },
        },
    )
    dispatch_started = perf_counter()
    await manager.broadcast(room_id, event)
    dispatch_ms = (perf_counter() - dispatch_started) * 1000
    await collector.increment_room("room_translation_results_total")
    await collector.observe_room_latency(
        queue_ms, result.asr_ms, result.translation_ms, dispatch_ms, end_to_end_ms
    )
    log_event(
        "room.translation_completed",
        room_id=room_id,
        participant_id=participant_id,
        event_id=turn["event_id"],
        sequence=turn["sequence"],
        room_status=(await manager.get_room(room_id)).status,
        source_language=result.source_language,
        target_language=result.target_language,
        audio_duration_ms=audio_duration_ms,
        asr_latency_ms=result.asr_ms,
        mt_latency_ms=result.translation_ms,
        end_to_end_latency_ms=end_to_end_ms,
    )


@app.websocket("/pipeline/stream")
async def stream_pipeline(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = websocket.query_params.get("session_id", str(uuid4()))
    language = websocket.query_params.get("language", "vi")
    vad = (
        SileroVAD(settings.vad_threshold, settings.vad_min_silence_ms)
        if settings.vad_mode == "silero"
        else EnergyVAD()
    )
    service = StreamingPipelineService(
        get_pipeline_service(),
        settings.audio_output_dir / "streams",
        vad,
        settings.partial_interval_chunks,
        get_metrics_collector(),
    )

    async def receive() -> bytes | None:
        try:
            return await websocket.receive_bytes()
        except WebSocketDisconnect:
            return None

    async def send(event: dict[str, object]) -> None:
        await websocket.send_json(event)

    await service.run(receive, send, session_id, language)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service=settings.app_name)


@app.get("/metrics", response_model=MetricsResponse)
async def metrics(
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
) -> MetricsResponse:
    return collector.snapshot()


@app.post("/asr", response_model=ASRResponse)
async def asr(
    request: AudioRequest, pipeline: Annotated[PipelineService, Depends(get_pipeline_service)]
) -> ASRResponse:
    return await pipeline.asr.transcribe(request)


@app.post("/translation", response_model=TranslationResponse)
async def translation(
    request: TranslationRequest, pipeline: Annotated[PipelineService, Depends(get_pipeline_service)]
) -> TranslationResponse:
    return await pipeline.translation.translate(request)


@app.post("/tts", response_model=TTSResponse)
async def tts(
    request: TTSRequest, pipeline: Annotated[PipelineService, Depends(get_pipeline_service)]
) -> TTSResponse:
    return await pipeline.tts.synthesize(request)


@app.post("/pipeline/process", response_model=PipelineResponse)
async def process_pipeline(
    request: AudioRequest,
    raw_request: Request,
    pipeline: Annotated[PipelineService, Depends(get_pipeline_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
) -> PipelineResponse:
    result = await pipeline.process(request, raw_request.state.request_id)
    await collector.record(result, wav_duration_ms(request.audio_path))
    return result


@app.post("/pipeline/upload", response_model=PipelineResponse)
async def upload_pipeline(
    raw_request: Request,
    pipeline: Annotated[PipelineService, Depends(get_pipeline_service)],
    collector: Annotated[MetricsCollector, Depends(get_metrics_collector)],
    audio: Annotated[UploadFile, File()],
    session_id: Annotated[str, Form()],
    speaker: Annotated[str, Form()] = "speaker_a",
    language: Annotated[str | None, Form()] = None,
) -> PipelineResponse:
    upload_dir = settings.audio_output_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "recording.webm").suffix
    path = upload_dir / f"{uuid4()}{suffix}"
    path.write_bytes(await audio.read())
    request = AudioRequest(
        session_id=session_id, speaker=speaker, language=language, audio_path=str(path)
    )
    result = await pipeline.process(request, raw_request.state.request_id)
    await collector.record(result)
    return result
