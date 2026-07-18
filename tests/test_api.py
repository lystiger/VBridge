from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.dependencies import get_metrics_collector, get_pipeline_service
from apps.api.main import app
from services.asr import MockASRService
from services.metrics import MetricsCollector
from services.pipeline import PipelineService
from services.translation import MockTranslationService
from services.tts import MockTTSService


def make_client(tmp_path: Path) -> TestClient:
    collector = MetricsCollector()
    app.dependency_overrides[get_pipeline_service] = lambda: PipelineService(
        MockASRService(), MockTranslationService(), MockTTSService(tmp_path)
    )
    app.dependency_overrides[get_metrics_collector] = lambda: collector
    return TestClient(app)


def test_health_endpoint(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_pipeline_and_metrics_endpoints(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/pipeline/process",
            json={
                "session_id": "session",
                "speaker": "speaker",
                "language": "vi",
                "audio_path": "clip.wav",
            },
        )
        metrics = client.get("/metrics")
        prometheus = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert response.json()["translation"] == "Hello"
    assert response.headers["x-request-id"]
    assert metrics.json()["request_count"] == 1
    assert prometheus.status_code == 200
    assert "vbridge_pipeline_requests_total 1" in prometheus.text
    assert "vbridge_inference_capacity 1" in prometheus.text


def test_upload_endpoint(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/pipeline/upload",
            data={"session_id": "upload-session", "speaker": "speaker", "language": "en"},
            files={"audio": ("recording.webm", b"audio", "audio/webm")},
        )
    assert response.status_code == 200
    assert response.json()["translation"] == "Xin chào"
