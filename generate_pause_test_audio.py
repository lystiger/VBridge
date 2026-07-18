"""
Tạo 1 file audio có khoảng lặng dài xen giữa (nói - im lặng 5s - nói tiếp)
để test khả năng chống hallucination của VAD/Whisper khi gặp khoảng lặng.

File này KHÔNG có đáp án chuẩn tương ứng trong test_dialogues.md (vì là file
ghép nhân tạo, không phải 1 đoạn hội thoại có sẵn) - nên tune_vad_whisper_scored.py
sẽ không tính được % chính xác cho nó, chỉ in ra transcript + cờ hallucination
để bạn tự đọc, kiểm tra xem model có "bịa chữ" trong đoạn im lặng không.

Cài đặt: pip install pydub
Chạy: python3 generate_pause_test_audio.py
"""
from pathlib import Path

from pydub import AudioSegment

# Dùng thẳng ffmpeg đi kèm gói imageio-ffmpeg (cài qua pip), không cần PATH
try:
    import imageio_ffmpeg
    AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    pass  # nếu chưa cài imageio-ffmpeg, dùng ffmpeg hệ thống như bình thường

CLEAN_DIR = Path("dataset/audio/clean")
OUTPUT = Path("test_audio/12_pause_test.wav")

SILENCE_MS = 5000  # 5 giây im lặng thật (không phải nhiễu nền, để test đúng case VAD)


def main():
    clip1 = AudioSegment.from_wav(CLEAN_DIR / "doan01_clean.wav")
    clip2 = AudioSegment.from_wav(CLEAN_DIR / "doan02_clean.wav")

    # Silence thật sự (không phải nhiễu) - đúng chuẩn 16kHz mono như các file khác
    silence = AudioSegment.silent(duration=SILENCE_MS, frame_rate=16000)

    combined = clip1 + silence + clip2
    combined = combined.set_frame_rate(16000).set_channels(1)

    Path("test_audio").mkdir(exist_ok=True)
    combined.export(OUTPUT, format="wav")
    print(f"Đã tạo {OUTPUT} — dài {len(combined)/1000:.1f}s "
          f"(gồm: câu 1 + {SILENCE_MS/1000:.0f}s im lặng + câu 2)")
    print("File này sẽ được tune_vad_whisper_scored.py chạy qua 9 tổ hợp, "
          "nhưng KHÔNG tính % chính xác - bạn cần tự đọc transcript in ra để "
          "kiểm tra xem model có tự bịa chữ trong đoạn im lặng không.")


if __name__ == "__main__":
    main()