"""
Sanity check — chạy 1 file, 1 model NHỎ NHẤT (tiny) trước khi chạy cả ma trận
90-100 file. Nếu bước này lỗi, sửa xong mới chạy full — tránh mất 30-60 phút
chờ rồi mới phát hiện lỗi từ đầu.
"""
import time

from faster_whisper import WhisperModel

print("Đang tải model tiny...")
t0 = time.time()
model = WhisperModel("tiny", device="cpu", compute_type="int8")
print(f"Tải xong sau {time.time()-t0:.1f}s\n")

# Đổi đường dẫn này thành đúng 1 file thật trong dataset/audio/clean/ của bạn
TEST_FILE = "dataset/audio/clean/doan01_clean.wav"

print(f"Đang test file: {TEST_FILE}")
t0 = time.time()
segments, info = model.transcribe(TEST_FILE, language="vi", beam_size=1)
text = " ".join(seg.text.strip() for seg in segments)
latency = time.time() - t0

print(f"\nKết quả: {text}")
print(f"Thời gian xử lý: {latency:.2f}s")
print("\n✅ Nếu thấy dòng trên, pipeline ASR hoạt động — an toàn để chạy full ma trận.")
