

import collections
import webrtcvad
import numpy as np

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30  # webrtcvad chỉ chấp nhận 10/20/30ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2):
        """
        aggressiveness: 0-3, càng cao càng "khó tính" khi coi là có tiếng nói
        (giúp lọc nhiễu nền tốt hơn ở mức 2-3 cho phòng họp ồn)
        """
        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame_bytes: bytes) -> bool:
        return self.vad.is_speech(frame_bytes, SAMPLE_RATE)

    def segment_audio(self, audio_np: np.ndarray, padding_ms: int = 300):
        """
        Nhận toàn bộ audio (float32, -1..1), trả về list các đoạn (start, end) có tiếng nói.
        padding_ms: giữ thêm 1 chút audio 2 đầu để không cắt cụt từ.
        """
        audio_int16 = (audio_np * 32768).astype(np.int16)
        num_padding_frames = padding_ms // FRAME_DURATION_MS
        ring_buffer = collections.deque(maxlen=num_padding_frames)

        segments = []
        triggered = False
        voiced_frames = []
        frame_start_idx = 0

        num_frames = len(audio_int16) // FRAME_SIZE
        for i in range(num_frames):
            frame = audio_int16[i * FRAME_SIZE:(i + 1) * FRAME_SIZE]
            frame_bytes = frame.tobytes()
            is_speech = self.is_speech(frame_bytes)

            if not triggered:
                ring_buffer.append((i, is_speech))
                num_voiced = len([f for f in ring_buffer if f[1]])
                if num_voiced > 0.8 * ring_buffer.maxlen:
                    triggered = True
                    frame_start_idx = ring_buffer[0][0]
                    ring_buffer.clear()
            else:
                voiced_frames.append(i)
                ring_buffer.append((i, is_speech))
                num_unvoiced = len([f for f in ring_buffer if not f[1]])
                if num_unvoiced > 0.8 * ring_buffer.maxlen:
                    triggered = False
                    segments.append((frame_start_idx * FRAME_SIZE, i * FRAME_SIZE))
                    ring_buffer.clear()
                    voiced_frames = []

        if triggered:
            segments.append((frame_start_idx * FRAME_SIZE, num_frames * FRAME_SIZE))

        return segments