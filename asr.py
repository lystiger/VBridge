
from faster_whisper import WhisperModel

# Chọn size model theo tốc độ máy:
# tiny / base / small / medium / large-v3
# Khuyên dùng "small" cho laptop CPU, "medium" nếu có GPU
MODEL_SIZE = "small"

class ASREngine:
    def __init__(self, model_size: str = MODEL_SIZE, device: str = "cpu", compute_type: str = "int8"):
        """
        device: "cpu" hoặc "cuda" (nếu có GPU, đổi compute_type="float16" để nhanh hơn)
        compute_type "int8" giúp chạy nhanh trên CPU, giảm nhẹ độ chính xác
        """
        print(f"[ASR] Loading faster-whisper model '{model_size}' on {device}...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("[ASR] Model loaded.")

    def transcribe(self, audio_np, language: str = None):
        """
        audio_np: numpy float32 array, mono, 16kHz
        language: "vi" hoặc "en" nếu biết trước, None để auto-detect
        Trả về: (text, detected_language)
        """
        segments, info = self.model.transcribe(
            audio_np,
            language=language,
            beam_size=5,
            vad_filter=True,               # faster-whisper có VAD tích hợp sẵn, lọc khoảng lặng
            condition_on_previous_text=False,  # KHÔNG dùng câu trước làm ngữ cảnh - tránh khuếch đại lặp
            compression_ratio_threshold=2.4,   # phát hiện & loại đoạn "lặp bất thường" (nén tốt = lặp nhiều)
            repetition_penalty=1.3,            # phạt token đã xuất hiện trong cùng lượt transcribe
            no_repeat_ngram_size=3,            # cấm lặp cụm 3 từ trở lên
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip(), info.language


if __name__ == "__main__":
    import sys
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"Test standalone - device: {device}, compute_type: {compute_type}")
    asr = ASREngine(device=device, compute_type=compute_type)
    if len(sys.argv) > 1:
        segments, info = asr.model.transcribe(sys.argv[1])
        for seg in segments:
            print(f"[{seg.start:.1f}s -> {seg.end:.1f}s] {seg.text}")
        print("Detected language:", info.language)
    else:
        print("Usage: python asr.py <audio_file.wav>")