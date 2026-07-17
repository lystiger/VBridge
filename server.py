

import io
import base64
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from asr import ASREngine
from translate import Translator
from tts import TTSEngine

app = FastAPI()

# --- Đường dẫn tuyệt đối, dựa trên vị trí file server.py này, không phụ thuộc
# vào thư mục cậu đứng khi gõ lệnh `uvicorn server:app` (tránh lỗi "Directory không tồn tại"
# khi chạy lệnh từ chỗ khác, hoặc khi cấu trúc thư mục project thay đổi).
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

# --- Tự động detect GPU (RTX 4060 hoặc GPU khác), fallback CPU nếu không có ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Models sẽ được load lúc server khởi động (startup event), không phải lúc import file ---
# Lý do: load ở module-level khiến bất kỳ ai import server.py (kể cả để test 1 hàm nhỏ)
# cũng phải tải hết model nặng trước - dùng startup event tách rõ "định nghĩa app" và "khởi động app".
_engines = {}


@app.on_event("startup")
async def load_models():
    print(f"=== Đang khởi động VBridge server, device: {DEVICE} ===")
    if DEVICE == "cpu":
        print("!!! CẢNH BÁO: không tìm thấy GPU, đang chạy CPU - sẽ chậm hơn nhiều. "
              "Kiểm tra: python3 -c \"import torch; print(torch.cuda.is_available())\"")
        print("Nếu máy có GPU nhưng vẫn báo False: có thể torch đang cài bản CPU-only, "
              "cần cài lại torch bản CUDA (xem hướng dẫn trong README).")

    # faster-whisper dùng compute_type riêng (không phải torch dtype):
    # "float16" tối ưu cho GPU, "int8" tối ưu cho CPU
    asr_compute_type = "float16" if DEVICE == "cuda" else "int8"

    _engines["asr"] = ASREngine(model_size="small", device=DEVICE, compute_type=asr_compute_type)
    _engines["translator"] = Translator(device=DEVICE)
    _engines["tts"] = TTSEngine(offline=False)  # đổi offline=True khi đã cài Coqui TTS
    print("=== Sẵn sàng nhận kết nối ===")


def webm_to_wav16k(webm_bytes: bytes) -> bytes:
    """
    Convert webm/opus bytes -> wav 16kHz mono bytes bằng ffmpeg (phải cài ffmpeg trên máy).
    Kiểm tra: chạy `ffmpeg -version` trong terminal, nếu chưa có thì:
      - macOS: brew install ffmpeg
      - Ubuntu: sudo apt install ffmpeg
      - Windows: choco install ffmpeg (hoặc tải binary thủ công)
    """
    process = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", "pipe:0",
            "-ar", "16000", "-ac", "1", "-f", "wav",
            "pipe:1",
        ],
        input=webm_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {process.stderr.decode(errors='ignore')}")
    return process.stdout


@app.get("/", response_class=HTMLResponse)
async def index():
    # Trang web đơn giản cho điện thoại: nút ghi âm + hiển thị transcript/bản dịch
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Điện thoại gửi lên: {"audio_base64": "...", "src_lang": "vi", "tgt_lang": "en"}
            data = await websocket.receive_json()

            # --- Mỗi lượt xử lý bọc riêng try/except: lỗi 1 lượt (audio hỏng, ffmpeg fail,
            # model lỗi...) chỉ báo lỗi về client và tiếp tục vòng lặp, KHÔNG làm sập
            # toàn bộ kết nối WebSocket (trước đây bị vậy - đây là bug đã sửa). ---
            try:
                audio_bytes = base64.b64decode(data["audio_base64"])
                src_lang = data.get("src_lang", "vi")
                tgt_lang = "en" if src_lang == "vi" else "vi"

                if len(audio_bytes) < 1000:  # audio quá ngắn/gần rỗng - lỗi hay gặp khi bấm nhả quá nhanh
                    await websocket.send_json({"error": "audio_too_short",
                                                "message": "Ghi âm quá ngắn, giữ nút lâu hơn 1 chút."})
                    continue

                # Browser ghi âm ra webm/opus - convert sang wav 16kHz mono bằng ffmpeg trước
                # (soundfile không đọc trực tiếp được webm)
                wav_bytes = webm_to_wav16k(audio_bytes)
                audio_np, sr = sf.read(io.BytesIO(wav_bytes))
                if audio_np.ndim > 1:
                    audio_np = audio_np.mean(axis=1)  # convert stereo -> mono nếu cần
                audio_np = audio_np.astype(np.float32)

                # --- Pipeline: ASR -> MT -> TTS ---
                text_src, detected_lang = _engines["asr"].transcribe(audio_np, language=src_lang)

                if not text_src.strip():
                    await websocket.send_json({"error": "no_speech_detected"})
                    continue

                text_translated = _engines["translator"].translate(text_src, src_lang, tgt_lang)
                audio_out_path = _engines["tts"].speak_to_file(text_translated, tgt_lang)
                audio_format = audio_out_path.rsplit(".", 1)[-1]  # "mp3" hoặc "wav" tùy engine đang dùng

                with open(audio_out_path, "rb") as f:
                    audio_out_b64 = base64.b64encode(f.read()).decode("utf-8")

                await websocket.send_json({
                    "original_text": text_src,
                    "translated_text": text_translated,
                    "src_lang": src_lang,
                    "tgt_lang": tgt_lang,
                    "audio_base64": audio_out_b64,
                    "audio_format": audio_format,
                })

            except Exception as e:
                # Lỗi trong 1 lượt xử lý (ffmpeg, ASR, MT, TTS...) - báo về client,
                # KHÔNG re-raise, để vòng lặp while True tiếp tục nghe lượt tiếp theo.
                print(f"!!! Lỗi khi xử lý 1 lượt: {type(e).__name__}: {e}")
                try:
                    await websocket.send_json({
                        "error": "processing_failed",
                        "message": f"{type(e).__name__}: {str(e)[:200]}",
                    })
                except Exception:
                    pass  # nếu gửi lỗi cũng fail (kết nối đã đứt thật) thì bỏ qua, vòng while sẽ tự thoát ở receive_json

    except WebSocketDisconnect:
        print("Client disconnected")


# Serve static files (index.html, JS) cho frontend điện thoại
if not STATIC_DIR.exists():
    raise RuntimeError(
        f"Không tìm thấy thư mục static tại: {STATIC_DIR}\n"
        f"Kiểm tra: index.html có đang nằm trong thư mục 'static/' cùng cấp với server.py không?\n"
        f"Nếu cấu trúc project đã đổi (index.html ở chỗ khác), sửa STATIC_DIR ở đầu file server.py."
    )
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")