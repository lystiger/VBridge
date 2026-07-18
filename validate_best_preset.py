import re
import time
from pathlib import Path

import pandas as pd
from faster_whisper import WhisperModel

# Cấu hình chốt sử dụng để Validate
CHOSEN_VAD = {
    "threshold": 0.65,
    "min_silence_duration_ms": 900,
    "min_speech_duration_ms": 300,
    "speech_pad_ms": 200,
}
CHOSEN_WHISPER = {
    "beam_size": 1,
    "no_speech_threshold": 0.75,
    "log_prob_threshold": -0.8,
    "compression_ratio_threshold": 2.2,
}

CLEAN_DIR = Path("dataset/audio/clean")
NOISY_DIR = Path("dataset/audio/noisy")
DIALOGUE_MD = Path("dataset/dialogues/test_dialogues.md")
WHISPER_MODEL_SIZE = "small"


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\sÀ-ỹ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def word_error_rate(hyp: str, ref: str) -> float:
    h, r = normalize(hyp).split(), normalize(ref).split()
    if not r:
        return 0.0 if not h else 1.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost
            )
    return d[len(r)][len(h)] / len(r)


def extract_id(filename_stem: str) -> str:
    match = re.search(r"(\d+)", filename_stem)
    return f"{int(match.group(1)):02d}" if match else filename_stem


def load_references() -> dict:
    text = DIALOGUE_MD.read_text(encoding="utf-8-sig")
    blocks = text.split("---")
    refs = {}
    for block in blocks:
        id_match = re.search(r"Đoạn\s*(\d+)", block)
        lang_match = re.search(r"LANG:\s*(\w+)", block)
        if not (id_match and lang_match):
            continue
        file_id = f"{int(id_match.group(1)):02d}"
        source_lang = "vi" if lang_match.group(1) == "vi2en" else "en"
        srcs = re.findall(r"S\d+_SRC:\s*(.+)", block)
        refs[file_id] = (" ".join(s.strip() for s in srcs), source_lang)
    return refs


def collect_all_files() -> list[dict]:
    files = []
    for f in sorted(CLEAN_DIR.glob("*.wav")):
        files.append(
            {
                "path": f,
                "file_id": extract_id(f.stem),
                "noise_type": "clean",
                "level": "clean",
            }
        )
    for noise_type_dir in sorted(NOISY_DIR.iterdir()):
        if not noise_type_dir.is_dir():
            continue
        for level_dir in sorted(noise_type_dir.iterdir()):
            if not level_dir.is_dir():
                continue
            for f in sorted(level_dir.glob("*.wav")):
                files.append(
                    {
                        "path": f,
                        "file_id": extract_id(f.stem),
                        "noise_type": noise_type_dir.name,
                        "level": level_dir.name,
                    }
                )
    return files


def main():
    references = load_references()
    print(f"Đang tải model '{WHISPER_MODEL_SIZE}'...")
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

    all_files = collect_all_files()
    print(f"Xác thực trên {len(all_files)} file (toàn bộ dataset)\n")

    rows = []
    for i, item in enumerate(all_files, 1):
        file_id = item["file_id"]
        if file_id not in references:
            continue
        ref_text, lang = references[file_id]

        t0 = time.time()
        segments_gen, _ = model.transcribe(
            str(item["path"]),
            language=lang,
            vad_filter=True,
            vad_parameters=CHOSEN_VAD,
            beam_size=CHOSEN_WHISPER["beam_size"],
            no_speech_threshold=CHOSEN_WHISPER["no_speech_threshold"],
            log_prob_threshold=CHOSEN_WHISPER["log_prob_threshold"],
            compression_ratio_threshold=CHOSEN_WHISPER[
                "compression_ratio_threshold"
            ],
        )
        segments = list(segments_gen)
        latency = time.time() - t0
        text = " ".join(s.text.strip() for s in segments)

        wer = word_error_rate(text, ref_text)
        accuracy = max(0.0, 1 - wer) * 100

        rows.append(
            {
                "file_id": file_id,
                "noise_type": item["noise_type"],
                "level": item["level"],
                "accuracy_pct": round(accuracy, 1),
                "latency_s": round(latency, 3),
            }
        )
        if i % 20 == 0:
            print(f"  ...đã xử lý {i}/{len(all_files)}")

    df = pd.DataFrame(rows)
    df.to_csv("final_validation_detail.csv", index=False)

    overall_acc = df["accuracy_pct"].mean()
    overall_latency = df["latency_s"].mean()

    by_level = df.groupby("level")["accuracy_pct"].mean().round(1)
    by_type = df.groupby("noise_type")["accuracy_pct"].mean().round(1)

    print("\n" + "=" * 60)
    print(f"KẾT QUẢ XÁC THỰC CUỐI CÙNG — trên {len(df)} file")
    print("=" * 60)
    print("✅ CẤU HÌNH ĐÃ SỬ DỤNG ĐỂ VALIDATE:")
    print(f"   VAD Cấu hình chốt:     {CHOSEN_VAD}")
    print(f"   Whisper Cấu hình chốt: {CHOSEN_WHISPER}")
    print("-" * 60)
    print(f"Độ chính xác trung bình TOÀN BỘ: {overall_acc:.1f}%")
    print(f"Độ trễ trung bình: {overall_latency:.2f}s")
    print(f"\nTheo mức độ nhiễu:\n{by_level.to_string()}")
    print(f"\nTheo loại nhiễu:\n{by_type.to_string()}")
    print(
        "\nĐã lưu final_validation_detail.csv — dùng số liệu "
        "này cho slide/báo cáo cuối cùng."
    )


if __name__ == "__main__":
    main()