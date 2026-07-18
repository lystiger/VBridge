import shutil
from pathlib import Path

TEST_AUDIO_DIR = Path("test_audio")
TEST_AUDIO_DIR.mkdir(exist_ok=True)

PICKS = [
    ("dataset/audio/clean/doan01_clean.wav", "01_clean.wav"),
    ("dataset/audio/clean/doan06_clean.wav", "02_clean.wav"),
    ("dataset/audio/noisy/cafe/level_light/doan02_clean.wav", "03_cafe_light.wav"),
    ("dataset/audio/noisy/cafe/level_medium/doan03_clean.wav", "04_cafe_medium.wav"),
    ("dataset/audio/noisy/cafe/level_heavy/doan04_clean.wav", "05_cafe_heavy.wav"),
    ("dataset/audio/noisy/office/level_light/doan05_clean.wav", "06_office_light.wav"),
    ("dataset/audio/noisy/office/level_medium/doan07_clean.wav", "07_office_medium.wav"),
    ("dataset/audio/noisy/office/level_heavy/doan08_clean.wav", "08_office_heavy.wav"),
    ("dataset/audio/noisy/street/level_light/doan09_clean.wav", "09_street_light.wav"),
    ("dataset/audio/noisy/street/level_medium/doan10_clean.wav", "10_street_medium.wav"),
    ("dataset/audio/noisy/street/level_heavy/doan01_clean.wav", "11_street_heavy.wav"),
]

for src, dst_name in PICKS:
    src_path = Path(src)
    if not src_path.exists():
        print(f"⚠️  Bỏ qua, không tồn tại: {src}")
        continue
    shutil.copy(src_path, TEST_AUDIO_DIR / dst_name)
    print(f"  Đã copy: {src} -> test_audio/{dst_name}")

print("\nXong. Kiểm tra: ls test_audio/")
print("Lưu ý: file có khoảng lặng cần tạo riêng bằng generate_pause_test_audio.py")