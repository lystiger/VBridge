import wave
from datetime import UTC, datetime
from pathlib import Path
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
    InMemoryRoomManager,
    InvalidRoomCodeError,
    Participant,
    Room,
    RoomFullError,
    RoomNotFoundError,
    RoomUnavailableError,
)
from services.sessions import (
    ParticipantNotFoundError as SessionParticipantNotFoundError,
    SessionManager,
    SessionNotFoundError,
)
from services.streaming import StreamingPipelineService
from services.vad import EnergyVAD, SileroVAD
from shared.config import get_settings
from shared.logging import configure_logging
from shared.schemas import (
    ASRResponse,
    AudioRequest,
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
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=settings.audio_output_dir), name="audio")


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
) -> RoomAccessResponse:
    room, participant = await manager.create_room(
        request.display_name, request.source_language, request.target_language
    )
    return room_access_response(manager, token_service, room, participant)


@app.post("/rooms/join", response_model=RoomAccessResponse)
async def join_room(
    request: JoinRoomRequest,
    manager: Annotated[InMemoryRoomManager, Depends(get_room_manager)],
    token_service: Annotated[RoomTokenService, Depends(get_room_token_service)],
) -> RoomAccessResponse:
    try:
        room, participant = await manager.join_room(
            request.room_code,
            request.display_name,
            request.source_language,
            request.target_language,
        )
    except InvalidRoomCodeError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    except RoomFullError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code}) from exc
    except RoomUnavailableError as exc:
        status_code = 410 if exc.code == "ROOM_EXPIRED" else 409
        raise HTTPException(status_code=status_code, detail={"code": exc.code}) from exc
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
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    claims = verify_bearer(authorization, token_service, room_id)
    room = await manager.get_room(room_id)
    if claims["participant_id"] not in room.participants:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
    sockets = await manager.close_room(room_id)
    event = {
        "type": "room.closed",
        "event_id": str(uuid4()),
        "room_id": room_id,
        "participant_id": "system",
        "sequence": 0,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {},
    }
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
