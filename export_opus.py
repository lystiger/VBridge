"""
Export + quantize 2 model OPUS-MT (vi->en và en->vi) sang ONNX INT8, đóng gói
sẵn thành 2 thư mục để bàn giao thẳng cho bên Android build/test ngay - không
cần train gì, chỉ cần chạy 1 lần.

Cài đặt cần thêm (nếu chưa có):
    pip install optimum[onnxruntime] transformers

LƯU Ý: script này cần tải model từ huggingface.co, nên máy chạy phải có mạng
ra internet bình thường (không giới hạn như môi trường sandbox này).
"""

import shutil
from pathlib import Path

from optimum.onnxruntime import ORTModelForSeq2SeqLM, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer

# --- Cấu hình ---
MODELS = {
    "vi2en": "Helsinki-NLP/opus-mt-vi-en",
    "en2vi": "Helsinki-NLP/opus-mt-en-vi",
}
OUTPUT_ROOT = Path("android_handoff_models")


def export_and_quantize(direction: str, model_id: str, output_root: Path):
    onnx_dir = output_root / direction / "onnx_fp32"
    quant_dir = output_root / direction / "onnx_int8"
    onnx_dir.mkdir(parents=True, exist_ok=True)
    quant_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== [{direction}] {model_id} ===")
    print("Đang export sang ONNX...")
    ort_model = ORTModelForSeq2SeqLM.from_pretrained(model_id, export=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    ort_model.save_pretrained(onnx_dir)
    tokenizer.save_pretrained(onnx_dir)

    fp32_size = _dir_size_mb(onnx_dir)
    print(f"ONNX fp32: {fp32_size:.1f} MB")

    print("Đang quantize INT8 (target arm64 cho điện thoại)...")
    qconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
    onnx_files = [f for f in onnx_dir.iterdir() if f.suffix == ".onnx"]
    if not onnx_files:
        raise RuntimeError(f"Không tìm thấy file .onnx nào trong {onnx_dir}")

    for f in onnx_files:
        print(f"  Quantizing {f.name}...")
        quantizer = ORTQuantizer.from_pretrained(onnx_dir, file_name=f.name)
        # file_suffix="" bắt buộc, nếu không ORTModelForSeq2SeqLM.from_pretrained()
        # sau này sẽ không tìm thấy đúng file khi load lại (xem export_onnx.py đã sửa
        # trước đó - cùng 1 bug với pipeline NLLB).
        quantizer.quantize(save_dir=quant_dir, quantization_config=qconfig, file_suffix="")

    # copy tokenizer/config sang thư mục quantized
    for f in onnx_dir.iterdir():
        if f.suffix != ".onnx":
            dst = quant_dir / f.name
            if not dst.exists():
                shutil.copy2(f, dst)

    int8_size = _dir_size_mb(quant_dir)
    print(f"ONNX INT8: {int8_size:.1f} MB (giảm {(1 - int8_size/fp32_size)*100:.0f}% so với fp32)")

    # --- Sanity check: load lại bản quantize, dịch thử 1 câu, đảm bảo không rỗng/không lỗi ---
    print("Sanity check bản quantize...")
    quant_model = ORTModelForSeq2SeqLM.from_pretrained(quant_dir)
    test_text = "Xin chào, rất vui được hợp tác." if direction == "vi2en" else "Hello, nice to meet you."
    inputs = tokenizer(test_text, return_tensors="pt")
    generated = quant_model.generate(**inputs, max_length=128, num_beams=4)
    result = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
    status = "OK" if result.strip() else "FAIL (output rỗng - KIỂM TRA LẠI)"
    print(f"  [{status}] '{test_text}' -> '{result}'")

    return quant_dir, int8_size, status == "OK"


def _dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)


def main():
    OUTPUT_ROOT.mkdir(exist_ok=True)
    summary = []

    for direction, model_id in MODELS.items():
        quant_dir, size_mb, ok = export_and_quantize(direction, model_id, OUTPUT_ROOT)
        summary.append((direction, model_id, quant_dir, size_mb, ok))

    print("\n" + "=" * 60)
    print("TÓM TẮT - bàn giao cho Android:")
    all_ok = True
    for direction, model_id, quant_dir, size_mb, ok in summary:
        status = "✓ OK" if ok else "✗ CẦN KIỂM TRA LẠI"
        print(f"  [{status}] {direction} ({model_id}): {quant_dir}/  (~{size_mb:.0f} MB)")
        all_ok = all_ok and ok

    if not all_ok:
        print("\n!!! Có model bị FAIL sanity check ở trên - KHÔNG giao bản đó cho Android "
              "cho tới khi debug xong, dùng tạm bản onnx_fp32/ chưa quantize thay thế.")
    else:
        print(f"\nCả 2 model đã sẵn sàng trong {OUTPUT_ROOT}/. Mỗi thư mục {OUTPUT_ROOT}/<direction>/onnx_int8/ "
              f"chứa đủ file .onnx + tokenizer để Android load thẳng qua ONNX Runtime Mobile.")
        print("Interface: text vào -> text ra, giống hệt model KD tự train sau này sẽ thay thế, "
              "nên bên Android không cần sửa code khi swap model.")


if __name__ == "__main__":
    main()