"""
Đóng gói model OPUS-MT (đã export+quantize bằng export_opus_mt_for_android.py) thành
gói bàn giao đúng chuẩn hợp đồng bên Android yêu cầu (xem tài liệu "HỢP ĐỒNG BÀN GIAO
MÔ HÌNH PHOMT DISTILLED CHO VBRIDGE").

QUAN TRỌNG - đọc trước khi chạy:
Model dùng ở đây là Helsinki-NLP/opus-mt-vi-en và opus-mt-en-vi (pretrained có sẵn),
KHÔNG PHẢI model PhoMT distilled từ NLLB mà nhóm đang tự train. Đây là gói bàn giao
TẠM THỜI để bên Android build/test luồng tích hợp ngay, trong lúc chờ model KD thật.
Contract JSON dưới đây ghi ĐÚNG sự thật này (provenance: OPUS-MT pretrained, không
phải distilled by our team) - không tự sửa description thành "distilled from NLLB"
nếu chưa thật sự train xong và thay model, kẻo bên Android hiểu nhầm nguồn gốc.

Vì OPUS-MT export ra NHIỀU file .onnx (encoder / decoder / decoder_with_past),
không phải 1 file "model.onnx" duy nhất như ví dụ đơn giản trong hợp đồng - script
này tự "introspect" (đọc trực tiếp) từng file .onnx bằng thư viện `onnx` để lấy
CHÍNH XÁC input/output tensor names, shapes, dtypes - không tự gõ tay số liệu
đoán mò, đúng như hợp đồng yêu cầu ("Không được copy nguyên các số mẫu nếu chưa
xác minh").

Cài đặt cần thêm:
    pip install onnx optimum[onnxruntime] transformers

Input: thư mục đã có sẵn từ export_opus_mt_for_android.py, ví dụ:
    android_handoff_models/vi2en/onnx_int8/
    android_handoff_models/en2vi/onnx_int8/

Output: 2 gói release đầy đủ, mỗi gói theo đúng cây thư mục hợp đồng yêu cầu:
    vbridge_opusmt_vi2en_release/
    vbridge_opusmt_en2vi_release/
"""

import hashlib
import json
import time
from pathlib import Path

import onnx
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoConfig, AutoTokenizer

# --- Cấu hình ---
SOURCE_DIRS = {
    "vi-en": Path("android_handoff_models/vi2en/onnx_int8"),
    "en-vi": Path("android_handoff_models/en2vi/onnx_int8"),
}
MODEL_HF_IDS = {
    "vi-en": "Helsinki-NLP/opus-mt-vi-en",
    "en-vi": "Helsinki-NLP/opus-mt-en-vi",
}
RELEASE_DIR_TEMPLATE = "vbridge_opusmt_{tag}_release"  # tag: vi2en / en2vi

ONNXRUNTIME_MOBILE_MIN_VERSION = "1.18.0"

# --- Target device (ĐÃ ĐỔI - không còn Snapdragon 845) ---
# Mức sàn: Helio G99 (octa-core, 2x Cortex-A76 + 6x Cortex-A55, không NPU riêng).
# Mức tốt: S22+ (Snapdragon 8 Gen 1, có NPU/Hexagon DSP).
# Pipeline dùng chung 1 đường CPU-only (whisper.cpp / ONNX Runtime CPU) cho cả 2 dòng
# chip, KHÔNG dùng tối ưu riêng theo hãng (vd Qualcomm QNN) để tránh phân nhánh code
# theo từng dòng máy - đổi lại thì bỏ lỡ phần tăng tốc NPU trên S22+, coi đây là hướng
# tối ưu thêm sau nếu có thời gian, không phải việc bắt buộc cho bản interim này.
TARGET_DEVICE_NOTE = (
    "Mức sàn: Helio G99 (không NPU riêng, chạy CPU-only). "
    "Mức tốt: Samsung Galaxy S22+ (Snapdragon 8 Gen 1, có NPU). "
    "Pipeline hiện dùng chung 1 đường CPU-only cho cả 2 dòng chip, chưa tận dụng "
    "NPU riêng của Snapdragon - có thể tối ưu thêm sau."
)

# --- ASR dự kiến dùng (không nằm trong gói OPUS-MT này, ghi lại để bên Android biết
# trước phần sẽ ghép vào pipeline VAD -> ASR -> MT -> TTS) ---
ASR_PLAN = {
    "model": "Whisper small (multilingual)",
    "runtime": "whisper.cpp (GGML, quantized Q5)",
    "source": "https://github.com/ggerganov/whisper.cpp",
    "model_weights": "https://huggingface.co/openai/whisper-small "
                      "(convert sang GGML theo hướng dẫn trong whisper.cpp/models/README.md, "
                      "hoặc dùng GGML build sẵn tại https://huggingface.co/ggerganov/whisper.cpp)",
    "note": (
        "Whisper tiny KHÔNG dùng vì độ chính xác tiếng Việt quá kém (~60% WER). "
        "Whisper small là điểm cân bằng cho tầm Helio G99/S22+ - base cũng chạy được "
        "nhưng small cho chất lượng tiếng Việt tốt hơn đáng kể với phần cứng hiện tại."
    ),
}
VAD_PLAN = {
    "model": "Silero VAD",
    "source": "https://github.com/snakers4/silero-vad",
    "note": "Dùng tham số runtime (threshold, min_silence_duration_ms...), không fine-tune.",
}

# 20 câu mẫu + vài edge case lấy từ tài liệu hợp đồng (mục 10 và 14), giữ nguyên để
# nhất quán 2 bên. Đây là bộ TẠM (~24 câu/chiều) - hợp đồng khuyến nghị tối thiểu 50,
# nên coi đây là điểm khởi đầu, mở rộng thêm sau khi có thời gian.
SAMPLE_CASES = {
    "vi-en": [
        ("vi_en_001", "greeting", "Xin chào, rất vui được gặp bạn."),
        ("vi_en_002", "short_reply", "Vâng, tôi đồng ý."),
        ("vi_en_003", "question", "Bạn có thể nghe rõ tôi không?"),
        ("vi_en_004", "meeting", "Chúng ta bắt đầu cuộc họp nhé."),
        ("vi_en_005", "date", "Cuộc họp tiếp theo sẽ diễn ra vào ngày 18 tháng 8."),
        ("vi_en_006", "correction", "Tôi nói ngày 18, không phải ngày 15."),
        ("vi_en_007", "quantity", "Chúng tôi cần đặt 2.500 sản phẩm."),
        ("vi_en_008", "money", "Ngân sách tối đa là 50.000 đô la."),
        ("vi_en_009", "negation", "Chúng tôi chưa nhận được tài liệu."),
        ("vi_en_010", "clarification", "Bạn có thể giải thích lại phần cuối không?"),
        ("vi_en_011", "delivery", "Lô hàng sẽ được giao vào thứ Hai tuần tới."),
        ("vi_en_012", "schedule", "Chúng ta có thể dời cuộc họp sang 3 giờ chiều không?"),
        ("vi_en_013", "confirmation", "Xin xác nhận rằng giá đã bao gồm thuế."),
        ("vi_en_014", "long_sentence",
         "Nếu chúng tôi nhận được bản thiết kế trước thứ Sáu, đội kỹ thuật có thể "
         "hoàn thành việc đánh giá vào đầu tuần sau."),
        ("vi_en_015", "technical", "Độ trễ trung bình của hệ thống hiện tại là khoảng bốn giây."),
        ("vi_en_016", "accent", "Tôi muốn kiểm tra khả năng xử lý tiếng Việt có đầy đủ dấu."),
        ("vi_en_017", "punctuation", "Anh nói: \"Chúng ta sẽ hoàn thành hôm nay\", đúng không?"),
        ("vi_en_018", "whitespace", "  Chúng   ta cần   xác nhận lại.  "),
        ("vi_en_019", "short_reply", "Được rồi."),
        ("vi_en_020", "interrupt", "Xin lỗi, tôi có thể ngắt lời một chút không?"),
        ("edge_vi_en_empty", "empty", ""),
        ("edge_vi_en_whitespace_only", "whitespace", "    "),
        ("edge_vi_en_percent", "percentage", "Tỷ lệ lỗi đã giảm xuống còn 2,5%."),
        ("edge_vi_en_single_word", "single_word", "Cảm ơn."),
    ],
    "en-vi": [
        ("en_vi_001", "greeting", "Hello, it is nice to meet you."),
        ("en_vi_002", "short_reply", "Yes, I agree."),
        ("en_vi_003", "question", "Can you hear me clearly?"),
        ("en_vi_004", "meeting", "Let us begin the meeting."),
        ("en_vi_005", "date", "The next meeting will take place on August 18."),
        ("en_vi_006", "correction", "I said the 18th, not the 15th."),
        ("en_vi_007", "quantity", "We need to order 2,500 products."),
        ("en_vi_008", "money", "The maximum budget is 50,000 dollars."),
        ("en_vi_009", "negation", "We have not received the documents yet."),
        ("en_vi_010", "clarification", "Could you explain the last part again?"),
        ("en_vi_011", "delivery", "The shipment will be delivered next Monday."),
        ("en_vi_012", "schedule", "Can we move the meeting to 3 p.m.?"),
        ("en_vi_013", "confirmation", "Please confirm that the price includes tax."),
        ("en_vi_014", "long_sentence",
         "If we receive the design before Friday, the engineering team can complete "
         "the review early next week."),
        ("en_vi_015", "technical", "The average latency of the current system is approximately four seconds."),
        ("en_vi_016", "punctuation", "You said, \"We will finish today,\" correct?"),
        ("en_vi_017", "whitespace", "  We   need to   confirm again.  "),
        ("en_vi_018", "short_reply", "All right."),
        ("en_vi_019", "interrupt", "Sorry, may I interrupt for a moment?"),
        ("en_vi_020", "agreement", "We can proceed with the current proposal."),
        ("edge_en_vi_empty", "empty", ""),
        ("edge_en_vi_whitespace_only", "whitespace", "    "),
        ("edge_en_vi_percent", "percentage", "The error rate has decreased to 2.5%."),
        ("edge_en_vi_proper_noun", "proper_noun", "Nguyen Duc Anh will present the VBridge demo."),
    ],
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def onnx_elem_type_name(elem_type: int) -> str:
    return {
        1: "float32", 2: "uint8", 3: "int8", 4: "uint16", 5: "int16",
        6: "int32", 7: "int64", 9: "bool", 10: "float16", 11: "double",
    }.get(elem_type, f"unknown({elem_type})")


def introspect_onnx(path: Path) -> dict:
    """Đọc trực tiếp graph ONNX để lấy input/output THẬT - không đoán/copy tay."""
    model = onnx.load(str(path))

    def tensor_info(value_info):
        dims = []
        for d in value_info.type.tensor_type.shape.dim:
            if d.dim_param:
                dims.append(d.dim_param)
            elif d.dim_value:
                dims.append(d.dim_value)
            else:
                dims.append("?")
        return {
            "name": value_info.name,
            "dtype": onnx_elem_type_name(value_info.type.tensor_type.elem_type),
            "shape": dims,
        }

    return {
        "opset": model.opset_import[0].version if model.opset_import else None,
        "inputs": [tensor_info(i) for i in model.graph.input],
        "outputs": [tensor_info(o) for o in model.graph.output],
    }


def build_release(direction: str, source_dir: Path, hf_id: str):
    tag = "vi2en" if direction == "vi-en" else "en2vi"
    release_root = Path(RELEASE_DIR_TEMPLATE.format(tag=tag))
    model_dir = release_root / "model"
    tokenizer_dir = release_root / "tokenizer"
    config_dir = release_root / "config"
    reference_dir = release_root / "reference"
    tests_dir = release_root / "tests"
    samples_dir = release_root / "samples"
    for d in (model_dir, tokenizer_dir, config_dir, reference_dir, tests_dir, samples_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Đóng gói [{direction}] từ {source_dir} ===")
    if not source_dir.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {source_dir} - chạy export_opus_mt_for_android.py trước."
        )

    # --- copy + checksum model files ---
    onnx_files = sorted(source_dir.glob("*.onnx"))
    if not onnx_files:
        raise RuntimeError(f"Không có file .onnx nào trong {source_dir}")

    model_file_entries = {}
    file_introspection = {}
    for f in onnx_files:
        dst = model_dir / f.name
        dst.write_bytes(f.read_bytes())
        checksum = sha256_of(dst)
        (model_dir / f"{f.name}.sha256").write_text(checksum + "\n")
        model_file_entries[f.stem] = f"model/{f.name}"
        file_introspection[f.name] = introspect_onnx(dst)
        print(f"  {f.name}: opset={file_introspection[f.name]['opset']}, "
              f"inputs={[i['name'] for i in file_introspection[f.name]['inputs']]}, "
              f"outputs={[o['name'] for o in file_introspection[f.name]['outputs']]}")

    # --- copy tokenizer + config files ---
    for f in source_dir.iterdir():
        if f.suffix != ".onnx" and not f.name.endswith(".sha256") and f.is_file():
            if f.name == "config.json":
                (config_dir / f.name).write_bytes(f.read_bytes())
            else:
                (tokenizer_dir / f.name).write_bytes(f.read_bytes())

    # --- lấy special token IDs THẬT từ config, không đoán ---
    hf_config = AutoConfig.from_pretrained(source_dir)
    tokenizer = AutoTokenizer.from_pretrained(source_dir)
    special_tokens = {
        "pad_token": tokenizer.pad_token,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token": tokenizer.eos_token,
        "eos_token_id": tokenizer.eos_token_id,
        "unk_token": tokenizer.unk_token,
        "unk_token_id": tokenizer.unk_token_id,
        "decoder_start_token_id": getattr(hf_config, "decoder_start_token_id", tokenizer.pad_token_id),
    }

    # --- model_contract.json ---
    total_size_bytes = sum(f.stat().st_size for f in model_dir.glob("*.onnx"))
    contract = {
        "contract_version": "1.0.0",
        "model": {
            "name": f"VBridge-OPUS-MT-{direction}-INTERIM",
            "version": "0.1.0-interim",
            "description": (
                f"Pretrained Helsinki-NLP OPUS-MT model ({hf_id}), NOT distilled by our "
                f"team. Used as an interim stand-in so the Android team can build/test the "
                f"integration pipeline while the actual PhoMT-distilled (NLLB teacher) "
                f"model is still in training."
            ),
            "provenance": "third_party_pretrained",
            "source_huggingface_id": hf_id,
            "framework": "pytorch",
            "export_format": "onnx_seq2seq_multi_file",
            "files": model_file_entries,
            "onnx_opset": next(iter(file_introspection.values()))["opset"] if file_introspection else None,
            "architecture": "encoder_decoder_transformer_marian",
            "quantization": {
                "enabled": True,
                "type": "int8_dynamic",
                "weight_dtype": "int8",
                "activation_dtype": "float32",
                "target": "arm64",
            },
            "file_size_bytes_total": total_size_bytes,
        },
        "task": {
            "type": "machine_translation",
            "supported_directions": [
                {
                    "source_language": direction.split("-")[0],
                    "target_language": direction.split("-")[1],
                    "direction_id": direction,
                    "prefix": None,
                }
            ],
        },
        "tokenizer": {
            "type": "marian_sentencepiece_or_bpe (xem file thực tế trong tokenizer/)",
            "files": [f"tokenizer/{f.name}" for f in tokenizer_dir.iterdir()],
            "normalization": "unknown_not_verified",
            "lowercase": False,
            "preserve_vietnamese_diacritics": True,
            "padding_side": tokenizer.padding_side,
            "truncation_side": tokenizer.truncation_side,
            "max_source_tokens": tokenizer.model_max_length,
            "max_target_tokens": tokenizer.model_max_length,
        },
        "special_tokens": special_tokens,
        "preprocessing": {
            "trim_whitespace": True,
            "collapse_internal_whitespace": True,
            "unicode_normalization": "NFKC",
            "remove_control_characters": True,
            "preserve_case": True,
            "preserve_punctuation": True,
            "empty_input_behavior": "return_empty",
        },
        "runtime": {
            "recommended_android_runtime": "onnxruntime-mobile",
            "minimum_onnxruntime_version": ONNXRUNTIME_MOBILE_MIN_VERSION,
            "preferred_execution_provider": "cpu",
            "fallback_execution_provider": "cpu",
            "threading": {"intra_op_num_threads": 2, "inter_op_num_threads": 1},
        },
        # Tensor I/O THẬT của từng file, đọc trực tiếp từ ONNX graph (không đoán):
        "onnx_files_io": file_introspection,
        "generation": {
            "method": "greedy",
            "beam_size": 1,
            "max_new_tokens": 128,
            "min_new_tokens": 1,
            "length_penalty": 1.0,
            "repetition_penalty": 1.0,
            "no_repeat_ngram_size": 0,
            "early_stopping_on_eos": True,
        },
        "postprocessing": {
            "skip_special_tokens": True,
            "clean_up_tokenization_spaces": True,
            "strip_output": True,
            "preserve_terminal_punctuation": True,
        },
        "quality": {
            "evaluation_set_name": "vbridge_golden_v0_interim",
            "metrics": {
                "bleu_vi_en": None, "bleu_en_vi": None,
                "comet_vi_en": None, "comet_en_vi": None,
            },
            "note": "Chưa đo BLEU/COMET chính thức cho bản OPUS-MT này - chỉ có sanity check dịch không rỗng.",
        },
        "performance": {
            "target_devices": {
                "minimum": "Helio G99 (octa-core, 2x Cortex-A76 + 6x Cortex-A55, không NPU riêng)",
                "reference": "Samsung Galaxy S22+ (Snapdragon 8 Gen 1, có NPU/Hexagon DSP)",
                "note": TARGET_DEVICE_NOTE,
            },
            "reference_device": "TBD (đo trên máy dev x86, chưa phải Helio G99/S22+ thật - "
                                 "cần đo lại trên thiết bị thật sau khi Android build xong)",
            "reference_runtime": "Python ONNX Runtime CPU (optimum ORTModelForSeq2SeqLM)",
            "mean_latency_ms": None,
            "p95_latency_ms": None,
            "peak_ram_mb": None,
        },
        "compatibility": {
            "min_android_api": 24,
            "supported_abis": ["arm64-v8a"],
            "target_device_minimum": "Helio G99",
            "target_device_reference": "Samsung Galaxy S22+",
        },
        "pipeline_context": {
            "note": "Model MT trong gói này là 1 phần của pipeline VAD -> ASR -> MT -> TTS. "
                    "VAD và ASR KHÔNG nằm trong gói này (chỉ là model dịch text->text), "
                    "ghi lại đây để bên Android biết trước sẽ cần tích hợp thêm 2 model đó.",
            "vad_plan": VAD_PLAN,
            "asr_plan": ASR_PLAN,
        },
        "limitations": [
            "Model KHÔNG được train/distill bởi nhóm - là pretrained OPUS-MT gốc.",
            "Không chuyên biệt cho domain doanh nghiệp/hội thoại VBridge.",
            "Chỉ hỗ trợ 1 chiều dịch mỗi model file - cần 2 model riêng cho 2 chiều.",
            "Chưa có số liệu BLEU/COMET chính thức.",
            "Chưa đo latency/RAM trên thiết bị Helio G99/S22+ thật.",
            "Sẽ được THAY THẾ bởi model PhoMT distilled (NLLB teacher) khi train xong.",
        ],
        "delivery": {
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "created_by": "MODEL_TEAM_NAME",
            "contact": "TEAM_CONTACT",
            "git_commit": "N/A - third-party model, not from our training repo",
        },
    }
    (config_dir / "model_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (config_dir / "generation_config.json").write_text(
        json.dumps(contract["generation"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    model_card = f"""# Model Card - VBridge OPUS-MT Interim ({direction})

## Tên mô hình
VBridge-OPUS-MT-{direction}-INTERIM

## Trạng thái
**TẠM THỜI** - dùng để Android build/test luồng tích hợp trong lúc chờ model PhoMT
distilled (NLLB teacher) train xong. SẼ BỊ THAY THẾ.

## Nguồn gốc
Pretrained model từ Helsinki-NLP: `{hf_id}`. KHÔNG do nhóm tự train hay distill.

## Teacher / Student / Method
Không áp dụng cho bản này (không phải sản phẩm distillation của nhóm).

## Hướng dịch hỗ trợ
{direction}

## Dataset / training
Không áp dụng - dùng nguyên checkpoint public.

## Evaluation metrics
Chưa đo BLEU/COMET chính thức. Chỉ có sanity check dịch không rỗng trên vài câu mẫu.

## Known limitations
- Không chuyên biệt domain doanh nghiệp.
- Chỉ 1 chiều/model.
- Chưa benchmark trên thiết bị Android thật.

## Export / Quantization
ONNX (multi-file: encoder/decoder/decoder_with_past), quantize INT8 dynamic, target arm64.

## Kích thước
{total_size_bytes / (1024*1024):.1f} MB (tổng các file .onnx, đã quantize)

## Target device (ĐÃ ĐỔI - không còn Snapdragon 845)
- **Mức sàn:** Helio G99 (octa-core, 2x Cortex-A76 + 6x Cortex-A55, không có NPU riêng - chạy CPU-only)
- **Mức tốt:** Samsung Galaxy S22+ (Snapdragon 8 Gen 1, có NPU/Hexagon DSP)
- {TARGET_DEVICE_NOTE}
- Model MT trong gói này (ONNX + ONNX Runtime Mobile CPU) không phụ thuộc NPU, chạy được trên cả 2 mức máy.

## Pipeline tổng thể (model này chỉ là 1 phần)
Luồng đầy đủ dự kiến: **VAD → ASR → MT (model trong gói này) → TTS**.
VAD và ASR KHÔNG nằm trong gói bàn giao này (gói này chỉ có model dịch text→text),
ghi lại đây để bên Android biết trước và chuẩn bị tích hợp thêm:

- **VAD:** {VAD_PLAN['model']} — {VAD_PLAN['source']}
  ({VAD_PLAN['note']})
- **ASR:** {ASR_PLAN['model']}, chạy qua {ASR_PLAN['runtime']}
  - Source runtime: {ASR_PLAN['source']}
  - Model weights: {ASR_PLAN['model_weights']}
  - Lưu ý: {ASR_PLAN['note']}
- **TTS:** dùng `TextToSpeech` API có sẵn của Android, không cần model riêng.
"""
    (config_dir / "model_card.md").write_text(model_card, encoding="utf-8")

    # --- reference/infer_reference.py ---
    ref_script = '''"""
Reference inference cho model VBridge OPUS-MT interim - dùng optimum
ORTModelForSeq2SeqLM làm engine (đã tự xử lý đúng encoder/decoder/decoder_with_past
+ KV-cache), để làm NGUỒN THAM CHIẾU cho Android so sánh output/latency.

Lưu ý: tensor I/O tầng thấp (raw ONNX Runtime, không qua optimum) mà Android cần để
tự implement bằng Kotlin/Java được liệt kê CHÍNH XÁC (đọc trực tiếp từ graph, không
đoán) trong config/model_contract.json, phần "onnx_files_io".
"""
import argparse
import json
import time
from pathlib import Path

from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoTokenizer


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=Path(__file__).resolve().parents[1] / "model")
    parser.add_argument("--text", type=str, required=True)
    parser.add_argument("--direction", type=str, required=True)
    args = parser.parse_args()

    model = ORTModelForSeq2SeqLM.from_pretrained(args.model_dir)
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)

    text = normalize_text(args.text)
    if not text:
        print(json.dumps({
            "direction": args.direction, "source_text": text,
            "input_ids": [], "output_ids": [], "translation": "",
            "latency_ms": 0.0,
        }, ensure_ascii=False, indent=2))
        return

    inputs = tokenizer(text, return_tensors="pt")

    started = time.perf_counter()
    generated = model.generate(**inputs, max_length=128, num_beams=1)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    translation = tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()

    result = {
        "direction": args.direction,
        "source_text": text,
        "input_ids": inputs["input_ids"][0].tolist(),
        "output_ids": generated[0].tolist(),
        "translation": translation,
        "latency_ms": round(elapsed_ms, 2),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
'''
    (reference_dir / "infer_reference.py").write_text(ref_script, encoding="utf-8")
    (reference_dir / "requirements.txt").write_text(
        "optimum[onnxruntime]\ntransformers\nonnx\n", encoding="utf-8"
    )
    (reference_dir / "expected_environment.txt").write_text(
        "Python: 3.10+\nOS: bất kỳ (Linux/Windows/Mac)\nCPU runtime: ONNX Runtime CPUExecutionProvider\n"
        "GPU required: No\n", encoding="utf-8"
    )

    # --- chạy inference thật để lấy golden test cases (input_ids/output_ids/translation/latency thật) ---
    print("  Đang chạy inference thật để tạo golden test cases (có thể mất chút thời gian)...")
    model = ORTModelForSeq2SeqLM.from_pretrained(source_dir)
    golden_lines = []
    samples = []
    for case_id, category, text in SAMPLE_CASES[direction]:
        norm = normalize_text(text)
        if not norm:
            entry = {
                "id": case_id, "direction": direction, "category": category,
                "source_text": text, "normalized_source_text": norm,
                "input_ids": [], "output_ids": [], "reference_model_output": "",
                "expected_output_language": direction.split("-")[1],
                "exact_match_required": True, "semantic_match_required": False,
                "max_allowed_output_tokens": 32, "reference_latency_ms": 0.0,
                "notes": "empty/whitespace input - expect empty output",
            }
        else:
            inputs = tokenizer(norm, return_tensors="pt")
            started = time.perf_counter()
            generated = model.generate(**inputs, max_length=128, num_beams=1)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            translation = tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
            entry = {
                "id": case_id, "direction": direction, "category": category,
                "source_text": text, "normalized_source_text": norm,
                "input_ids": inputs["input_ids"][0].tolist(),
                "output_ids": generated[0].tolist(),
                "reference_model_output": translation,
                "expected_output_language": direction.split("-")[1],
                "exact_match_required": False,  # OPUS-MT chưa fine-tune domain, để semantic match cho an toàn
                "semantic_match_required": True,
                "max_allowed_output_tokens": 128,
                "reference_latency_ms": round(elapsed_ms, 2),
                "notes": "",
            }
        golden_lines.append(json.dumps(entry, ensure_ascii=False))
        samples.append(entry)

    (tests_dir / "golden_test_cases.jsonl").write_text("\n".join(golden_lines) + "\n", encoding="utf-8")
    (tests_dir / "golden_test_summary.md").write_text(
        f"# Golden test cases - {direction}\n\nTổng số case: {len(samples)}\n"
        f"(TẠM THỜI - hợp đồng khuyến nghị tối thiểu 50 case, đây mới có "
        f"{len(samples)} case cơ bản + edge case, cần bổ sung thêm sau.)\n",
        encoding="utf-8",
    )
    samples_filename = "vi_en_examples.json" if direction == "vi-en" else "en_vi_examples.json"
    (samples_dir / samples_filename).write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- tests/test_reference_inference.py (chuyển thẳng từ hợp đồng, chỉnh path) ---
    test_script = '''"""So khớp output thực tế với golden_test_cases.jsonl (semantic match, không exact match
vì OPUS-MT chưa fine-tune domain)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden_test_cases.jsonl"
SCRIPT = ROOT / "reference" / "infer_reference.py"


def normalize(text: str) -> str:
    return " ".join(text.strip().split()).casefold()


def main() -> None:
    failed = []
    with GOLDEN.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--direction", case["direction"], "--text", case["source_text"]],
                capture_output=True, text=True, check=True,
            )
            actual = normalize(json.loads(result.stdout)["translation"])
            expected = normalize(case["reference_model_output"])
            if actual != expected:
                failed.append({"id": case["id"], "expected": expected, "actual": actual})
    if failed:
        print(json.dumps(failed, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print("All golden test cases reproduced identically by reference script.")


if __name__ == "__main__":
    main()
'''
    (tests_dir / "test_reference_inference.py").write_text(test_script, encoding="utf-8")

    print(f"  Hoàn thành: {release_root}/  ({len(samples)} golden cases, "
          f"{len(onnx_files)} file .onnx, {total_size_bytes/(1024*1024):.1f} MB)")
    return release_root


def main():
    released = []
    for direction, source_dir in SOURCE_DIRS.items():
        hf_id = MODEL_HF_IDS[direction]
        released.append(build_release(direction, source_dir, hf_id))

    print("\n" + "=" * 60)
    print("XONG. Gửi cho Android 2 thư mục sau (nén lại trước khi gửi):")
    for r in released:
        print(f"  - {r}/")
    print("\nNHỚ nói rõ với Android: đây là model OPUS-MT TẠM THỜI (không phải PhoMT distilled "
          "thật), xem field 'limitations' trong model_contract.json của từng gói.")
    print(f"\nTarget device (đã đổi): {TARGET_DEVICE_NOTE}")
    print(f"ASR dự kiến (chưa nằm trong gói này): {ASR_PLAN['model']} qua {ASR_PLAN['runtime']}")
    print(f"  Runtime: {ASR_PLAN['source']}")
    print(f"  Weights: {ASR_PLAN['model_weights']}")
    print("Chi tiết đầy đủ đã nằm trong config/model_card.md và config/model_contract.json "
          "(field 'pipeline_context') của mỗi gói.")


if __name__ == "__main__":
    main()