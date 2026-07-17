import wave
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.dependencies import get_metrics_collector, get_pipeline_service
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.streaming import StreamingPipelineService
from services.vad import EnergyVAD, SileroVAD
from shared.config import get_settings
from shared.logging import configure_logging
from shared.schemas import (
    ASRResponse,
    AudioRequest,
    HealthResponse,
    MetricsResponse,
    PipelineResponse,
    TranslationRequest,
    TranslationResponse,
    TTSRequest,
    TTSResponse,
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
