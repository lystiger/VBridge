from abc import ABC, abstractmethod
from asyncio import to_thread


class VoiceActivityDetector(ABC):
    @abstractmethod
    async def feed(self, pcm: bytes) -> bool: ...

    @abstractmethod
    def reset(self) -> None: ...


class EnergyVAD(VoiceActivityDetector):
    def __init__(self, silence_chunks: int = 8) -> None:
        self.silence_chunks = silence_chunks
        self._silent = 0
        self._speech = False

    async def feed(self, pcm: bytes) -> bool:
        import math
        import struct

        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm[: len(pcm) // 2 * 2])
        rms = math.sqrt(sum(value * value for value in samples) / max(len(samples), 1))
        quiet = rms < 350
        self._speech = self._speech or not quiet
        self._silent = self._silent + 1 if quiet else 0
        return self._speech and self._silent >= self.silence_chunks

    def reset(self) -> None:
        self._silent = 0
        self._speech = False


class SileroVAD(VoiceActivityDetector):
    """Streaming Silero ONNX VAD fed with signed 16-bit, 16 kHz mono PCM."""

    frame_samples = 512
    frame_bytes = frame_samples * 2

    def __init__(self, threshold: float = 0.3, min_silence_ms: int = 500) -> None:
        try:
            from silero_vad import VADIterator, load_silero_vad
        except ImportError as exc:
            raise RuntimeError("Silero VAD requires: pip install -e '.[vad]'") from exc
        self._torch = __import__("torch")
        model = load_silero_vad(onnx=True)
        self.iterator = VADIterator(
            model,
            threshold=threshold,
            sampling_rate=16_000,
            min_silence_duration_ms=min_silence_ms,
        )
        self._buffer = bytearray()

    async def feed(self, pcm: bytes) -> bool:
        self._buffer.extend(pcm)
        frames: list[bytes] = []
        while len(self._buffer) >= self.frame_bytes:
            frames.append(bytes(self._buffer[: self.frame_bytes]))
            del self._buffer[: self.frame_bytes]
        return await to_thread(self._run_frames, frames)

    def _run_frames(self, frames: list[bytes]) -> bool:
        for frame in frames:
            tensor = (
                self._torch.frombuffer(bytearray(frame), dtype=self._torch.int16).float() / 32768
            )
            event = self.iterator(tensor, return_seconds=True)
            if event and "end" in event:
                return True
        return False

    def reset(self) -> None:
        self.iterator.reset_states()
        self._buffer.clear()
