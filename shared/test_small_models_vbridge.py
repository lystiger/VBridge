"""
test_small_models.py — bản khớp đúng cấu trúc thư mục project VBridge.

Cấu trúc thật đang dùng:
  dataset/audio/clean/01.wav ... 10.wav
  dataset/audio/noisy/{cafe,office,street}/{level_heavy,level_light,level_medium}/01.wav...
  dataset/dialogues/test_dialogues.md

Đo 2 thứ: ĐỘ CHÍNH XÁC (Word Error Rate) và ĐỘ TRỄ (latency) — cho nhiều
model ASR nhỏ, trên toàn bộ file sạch + nhiễu.

Cài đặt: pip install faster-whisper pandas matplotlib
Chạy: python3 test_small_models.py
"""

import re
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from faster_whisper import WhisperModel

# ---------- ĐƯỜNG DẪN — khớp đúng cây thư mục VBridge của bạn ----------
CLEAN_DIR = Path("dataset/audio/clean")
NOISY_DIR = Path("dataset/audio/noisy")
DIALOGUE_MD = Path("dataset/dialogues/test_dialogues.md")

# Model NHỎ cần so sánh — bớt "small" nếu máy chạy chậm quá
MODELS_TO_TEST = ["tiny", "base", "small"]
DEVICE = "cpu"  # đổi "cuda" nếu có GPU rời
COMPUTE_TYPE = "int8"

# Thứ tự hiển thị trên biểu đồ — khớp đúng tên thư mục thật, KHÔNG đổi tên
LEVEL_ORDER = ["clean", "level_light", "level_medium", "level_heavy"]


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
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    return d[len(r)][len(h)] / len(r)


def load_references() -> dict:
    if not DIALOGUE_MD.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {DIALOGUE_MD} — kiểm tra lại đường dẫn thật trên máy bạn."
        )
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


def extract_id(filename_stem: str) -> str:
    """Lấy số thứ tự từ tên file, bất kể định dạng: 'doan01_clean' -> '01', '01' -> '01'."""
    match = re.search(r"(\d+)", filename_stem)
    if not match:
        return filename_stem
    return f"{int(match.group(1)):02d}"


def collect_test_files() -> list[dict]:
    files = []
    if not CLEAN_DIR.exists():
        raise FileNotFoundError(f"Không tìm thấy {CLEAN_DIR}")
    for f in sorted(CLEAN_DIR.glob("*.wav")):
        files.append(
            {"path": f, "file_id": extract_id(f.stem), "noise_type": "none", "level": "clean"}
        )

    if NOISY_DIR.exists():
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


def run():
    references = load_references()
    test_files = collect_test_files()

    n_clean = len([f for f in test_files if f["level"] == "clean"])
    n_noisy = len(test_files) - n_clean
    print(f"Tìm thấy {len(test_files)} file audio ({n_clean} sạch, {n_noisy} nhiễu)\n")

    if len(test_files) == 0:
        print("⚠️  KHÔNG tìm thấy file nào. Kiểm tra lại đường dẫn CLEAN_DIR/NOISY_DIR ở đầu file.")
        return

    all_rows = []

    for model_name in MODELS_TO_TEST:
        print(f"\n{'=' * 60}\nĐANG TẢI MODEL: {model_name}\n{'=' * 60}")
        t_load = time.time()
        model = WhisperModel(model_name, device=DEVICE, compute_type=COMPUTE_TYPE)
        print(f"Tải xong sau {time.time() - t_load:.1f}s")

        for i, item in enumerate(test_files, 1):
            file_id = item["file_id"]
            if file_id not in references:
                print(
                    f"  ⚠️  Bỏ qua {item['path']}: không tìm thấy đáp án cho id '{file_id}' "
                    f"trong test_dialogues.md"
                )
                continue
            ref_text, lang = references[file_id]

            t0 = time.time()
            segments, _ = model.transcribe(str(item["path"]), language=lang, beam_size=1)
            hyp_text = " ".join(seg.text.strip() for seg in segments)
            latency = time.time() - t0

            wer = word_error_rate(hyp_text, ref_text)
            accuracy = max(0.0, 1 - wer) * 100

            all_rows.append(
                {
                    "model": model_name,
                    "file_id": file_id,
                    "noise_type": item["noise_type"],
                    "level": item["level"],
                    "latency_s": round(latency, 3),
                    "accuracy_pct": round(accuracy, 1),
                    "hypothesis": hyp_text,
                    "reference": ref_text,
                }
            )
            if i % 10 == 0:
                print(f"  ...đã xử lý {i}/{len(test_files)} file")

        print(f"Xong model {model_name}")

    if not all_rows:
        print("\n⚠️  Không có kết quả nào được ghi lại — kiểm tra lại cảnh báo 'Bỏ qua' ở trên.")
        return

    df = pd.DataFrame(all_rows)
    df.to_csv("asr_model_comparison_detail.csv", index=False, encoding="utf-8")
    print(f"\nĐã lưu asr_model_comparison_detail.csv ({len(df)} dòng)")

    summary = (
        df.groupby(["model", "level"])
        .agg(
            avg_accuracy=("accuracy_pct", "mean"),
            avg_latency=("latency_s", "mean"),
            num_files=("file_id", "count"),
        )
        .reset_index()
    )
    summary.to_csv("asr_model_comparison_summary.csv", index=False)
    print("Đã lưu asr_model_comparison_summary.csv\n")
    print(summary.to_string(index=False))

    fig, ax = plt.subplots(figsize=(8, 5))
    for model_name in MODELS_TO_TEST:
        sub = summary[summary["model"] == model_name]
        sub = sub.set_index("level").reindex(LEVEL_ORDER).reset_index()
        ax.plot(sub["level"], sub["avg_accuracy"], marker="o", label=model_name)
    ax.set_xlabel("Mức độ nhiễu")
    ax.set_ylabel("Độ chính xác ASR trung bình (%)")
    ax.set_title("So sánh độ chính xác các model ASR theo mức độ nhiễu")
    ax.legend(title="Model")
    ax.set_ylim(0, 100)
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig("chart_model_comparison.png", dpi=150)
    print("\nĐã lưu chart_model_comparison.png")
    plt.show()


if __name__ == "__main__":
    run()
