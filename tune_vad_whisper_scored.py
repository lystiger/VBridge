import re
import time
from pathlib import Path

import pandas as pd
from faster_whisper import WhisperModel

AUDIO_DIR = Path("test_audio")
DIALOGUE_MD = Path("dataset/dialogues/test_dialogues.md")
WHISPER_MODEL_SIZE = "small"
LANGUAGE = None

VAD_PRESETS = {
    "nhay_cao": {
        "threshold": 0.35,
        "min_silence_duration_ms": 400,
        "min_speech_duration_ms": 200,
        "speech_pad_ms": 150,
    },
    "can_bang": {
        "threshold": 0.5,
        "min_silence_duration_ms": 650,
        "min_speech_duration_ms": 250,
        "speech_pad_ms": 150,
    },
    "bao_thu": {
        "threshold": 0.65,
        "min_silence_duration_ms": 900,
        "min_speech_duration_ms": 300,
        "speech_pad_ms": 200,
    },
}

WHISPER_PRESETS = {
    "mac_dinh": {
        "beam_size": 1,
        "no_speech_threshold": 0.6,
        "log_prob_threshold": -1.0,
        "compression_ratio_threshold": 2.4,
    },
    "chong_hallucination_manh": {
        "beam_size": 1,
        "no_speech_threshold": 0.75,
        "log_prob_threshold": -0.8,
        "compression_ratio_threshold": 2.2,
    },
    "chat_luong_cao_cham_hon": {
        "beam_size": 5,
        "no_speech_threshold": 0.6,
        "log_prob_threshold": -1.0,
        "compression_ratio_threshold": 2.4,
    },
}


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
    if not DIALOGUE_MD.exists():
        raise FileNotFoundError(f"Không tìm thấy {DIALOGUE_MD}")
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


def looks_like_hallucination(segments) -> list:
    flags = []
    for seg in segments:
        reasons = []
        if seg.compression_ratio > 2.4:
            reasons.append("compression_ratio cao")
        if seg.avg_logprob < -1.0:
            reasons.append("avg_logprob thấp")
        if seg.no_speech_prob > 0.6:
            reasons.append("no_speech_prob cao")
        if reasons:
            flags.append((seg.text.strip(), reasons))
    return flags


def run_one(model, audio_path, vad_params, whisper_params, language):
    started = time.perf_counter()
    segments_gen, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        vad_parameters=vad_params,
        beam_size=whisper_params["beam_size"],
        no_speech_threshold=whisper_params["no_speech_threshold"],
        log_prob_threshold=whisper_params["log_prob_threshold"],
        compression_ratio_threshold=whisper_params[
            "compression_ratio_threshold"
        ],
    )
    segments = list(segments_gen)
    elapsed = time.perf_counter() - started
    full_text = " ".join(seg.text.strip() for seg in segments).strip()
    flags = looks_like_hallucination(segments)
    return full_text, elapsed, len(flags)


def main():
    if not AUDIO_DIR.exists() or not any(AUDIO_DIR.iterdir()):
        print(
            f"!!! Chưa có file trong {AUDIO_DIR}/. "
            "Chạy setup_test_audio.py trước."
        )
        return

    references = load_references()
    print(f"Đang load Whisper model '{WHISPER_MODEL_SIZE}'...")
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

    audio_files = sorted(
        [
            f
            for f in AUDIO_DIR.iterdir()
            if f.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac")
        ]
    )
    print(f"Tìm thấy {len(audio_files)} file audio\n")

    rows = []
    # file không có đáp án chuẩn (vd file test khoảng lặng)
    # - vẫn chạy, chỉ không tính %
    no_ref_results = []
    for audio_path in audio_files:
        file_id = extract_id(audio_path.stem)
        has_ref = file_id in references

        if has_ref:
            ref_text, lang = references[file_id]
        else:
            ref_text, lang = None, "vi"
            print(
                f"ℹ️  {audio_path.name}: không có đáp án chuẩn — vẫn chạy "
                "để kiểm tra hallucination, không tính % chính xác"
            )

        effective_lang = LANGUAGE or lang
        print(f"Đang xử lý {audio_path.name}...")

        for vad_name, vad_params in VAD_PRESETS.items():
            for whisper_name, whisper_params in WHISPER_PRESETS.items():
                text, latency, n_flags = run_one(
                    model,
                    audio_path,
                    vad_params,
                    whisper_params,
                    effective_lang,
                )
                if has_ref:
                    wer = word_error_rate(text, ref_text)
                    accuracy = max(0.0, 1 - wer) * 100
                    rows.append(
                        {
                            "file": audio_path.name,
                            "vad_preset": vad_name,
                            "whisper_preset": whisper_name,
                            "accuracy_pct": round(accuracy, 1),
                            "latency_s": round(latency, 2),
                            "hallucination_flags": n_flags,
                        }
                    )
                else:
                    no_ref_results.append(
                        {
                            "file": audio_path.name,
                            "vad_preset": vad_name,
                            "whisper_preset": whisper_name,
                            "text": text,
                            "latency_s": round(latency, 2),
                            "hallucination_flags": n_flags,
                        }
                    )

    if no_ref_results:
        print("\n" + "=" * 70)
        print(
            "KẾT QUẢ FILE KHÔNG CÓ ĐÁP ÁN (vd file test khoảng lặng) — "
            "tự đọc để kiểm tra"
        )
        print("=" * 70)
        for r in no_ref_results:
            flag_marker = (
                f" ⚠️ {r['hallucination_flags']} cờ nghi ngờ"
                if r["hallucination_flags"]
                else " ✅ sạch"
            )
            print(
                f"[{r['vad_preset']} + {r['whisper_preset']}]"
                f"{flag_marker} ({r['latency_s']}s)"
            )
            print(f'   "{r["text"]}"')
        print()

    if not rows:
        print(
            "⚠️  Không có kết quả nào — kiểm tra lại tên file / "
            "test_dialogues.md."
        )
        return

    df = pd.DataFrame(rows)
    df.to_csv("vad_whisper_tuning_detail.csv", index=False, encoding="utf-8")

    summary = (
        df.groupby(["vad_preset", "whisper_preset"])
        .agg(
            avg_accuracy=("accuracy_pct", "mean"),
            avg_latency=("latency_s", "mean"),
            total_flags=("hallucination_flags", "sum"),
        )
        .reset_index()
        .sort_values("avg_accuracy", ascending=False)
    )
    summary.to_csv("vad_whisper_tuning_summary.csv", index=False)

    print("\n" + "=" * 70)
    print("BẢNG XẾP HẠNG — sắp theo độ chính xác trung bình, cao nhất lên đầu")
    print("=" * 70)
    print(summary.to_string(index=False))

    best = summary.iloc[0]
    print(
        f"\n✅ BỘ THAM SỐ TỐT NHẤT: VAD='{best['vad_preset']}' + "
        f"Whisper='{best['whisper_preset']}'"
    )
    print(
        f"   Độ chính xác trung bình: {best['avg_accuracy']:.1f}%  |  "
        f"Độ trễ trung bình: {best['avg_latency']:.2f}s  |  "
        f"Tổng cờ nghi ngờ hallucination: {int(best['total_flags'])}"
    )
    print("\nGiá trị số thật để gửi cho bên Android:")
    print(
        f"   VAD_PRESETS['{best['vad_preset']}'] = "
        f"{VAD_PRESETS[best['vad_preset']]}"
    )
    print(
        f"   WHISPER_PRESETS['{best['whisper_preset']}'] = "
        f"{WHISPER_PRESETS[best['whisper_preset']]}"
    )
    print(
        "\nĐã lưu vad_whisper_tuning_detail.csv và "
        "vad_whisper_tuning_summary.csv"
    )


if __name__ == "__main__":
    main()