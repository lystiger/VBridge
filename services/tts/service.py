import math
import struct
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from time import perf_counter

from shared.schemas import TTSRequest, TTSResponse


class TTSService(ABC):
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse: ...


class MockTTSService(TTSService):
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        started = perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{request.session_id}.wav"
        path = self.output_dir / filename
        self._write_tone(path)
        return TTSResponse(
            session_id=request.session_id,
            language=request.language,
            audio_url=f"/audio/{filename}",
            processing_ms=(perf_counter() - started) * 1000,
        )

    @staticmethod
    def _write_tone(path: Path) -> None:
        sample_rate = 16_000
        duration_seconds = 0.25
        with wave.open(str(path), "wb") as output:
            output.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
            frames = (
                struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
                for index in range(int(sample_rate * duration_seconds))
            )
            output.writeframes(b"".join(frames))
