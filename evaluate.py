"""
Bước 4: Đánh giá cuối cùng — so sánh TEACHER vs STUDENT trên test set thật
(test_real.jsonl - set này KHÔNG được dùng ở bất kỳ bước train/val nào trước đó,
đảm bảo đánh giá công bằng, không lạc quan giả tạo).

Đo 2 thứ:
1. BLEU score - chất lượng dịch (so với sacrebleu, thước đo chuẩn ngành)
2. Latency - thời gian dịch trung bình mỗi câu (đây là số liệu "wow" chính cho pitch)

Output: bảng so sánh in ra terminal + lưu JSON để cậu paste thẳng vào slide.
"""

import json
import time
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import sacrebleu

import config


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def translate_batch(model, tokenizer, texts, device, num_beams=4):
    tokenizer.src_lang = config.LANG_CODES["vi"]
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(config.LANG_CODES["en"])
    inputs = tokenizer(texts, return_tensors="pt", padding=True,
                        truncation=True, max_length=config.MAX_SEQ_LENGTH).to(device)
    with torch.no_grad():
        generated = model.generate(**inputs, forced_bos_token_id=forced_bos_token_id,
                                    max_length=config.MAX_SEQ_LENGTH, num_beams=num_beams)
    return tokenizer.batch_decode(generated, skip_special_tokens=True)


def evaluate_model(model_path, model_label, test_pairs, device, batch_size=8):
    print(f"\n--- Đang đánh giá: {model_label} ({model_path}) ---")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(device)
    model.eval()

    sources = [p["vi"] for p in test_pairs]
    references = [[p["en"] for p in test_pairs]]  # sacrebleu cần list-of-list cho multi-reference

    hypotheses = []
    per_sentence_latencies = []

    # Đo latency theo TỪNG CÂU (batch_size=1) vì đây mới đúng kịch bản real-time thực tế
    # (không phải throughput hàng loạt, mà độ trễ 1 lượt nói -> 1 lượt dịch)
    print("Đang đo latency per-sentence (batch=1, giống kịch bản real-time thật)...")
    for src in sources:
        start = time.time()
        hyp = translate_batch(model, tokenizer, [src], device, num_beams=config.TEACHER_NUM_BEAMS)[0]
        elapsed = time.time() - start
        hypotheses.append(hyp)
        per_sentence_latencies.append(elapsed)

    bleu = sacrebleu.corpus_bleu(hypotheses, references)
    avg_latency = sum(per_sentence_latencies) / len(per_sentence_latencies)
    p95_latency = sorted(per_sentence_latencies)[int(0.95 * len(per_sentence_latencies))]

    # Đếm số tham số - để show trong pitch model nhẹ đi bao nhiêu
    num_params = sum(p.numel() for p in model.parameters())

    result = {
        "model_label": model_label,
        "model_path": model_path,
        "bleu": round(bleu.score, 2),
        "avg_latency_ms": round(avg_latency * 1000, 1),
        "p95_latency_ms": round(p95_latency * 1000, 1),
        "num_params_millions": round(num_params / 1e6, 1),
        "num_test_sentences": len(test_pairs),
    }

    print(f"BLEU: {result['bleu']}")
    print(f"Latency trung bình: {result['avg_latency_ms']} ms/câu")
    print(f"Latency P95: {result['p95_latency_ms']} ms/câu")
    print(f"Số tham số: {result['num_params_millions']}M")

    # Giải phóng GPU memory trước khi load model tiếp theo
    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    return result, hypotheses


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    test_pairs = load_jsonl("data/test_real.jsonl")
    print(f"Test set: {len(test_pairs)} câu (chưa từng dùng để train/validate)")

    teacher_result, teacher_hyps = evaluate_model(
        config.TEACHER_MODEL, "Teacher (NLLB-600M gốc)", test_pairs, device,
    )
    student_result, student_hyps = evaluate_model(
        f"{config.OUTPUT_DIR}/final", "Student (đã distill)", test_pairs, device,
    )

    # --- Bảng so sánh cuối - copy thẳng số liệu này vào slide pitch ---
    print("\n" + "=" * 60)
    print("BẢNG SO SÁNH CUỐI CÙNG (dùng cho pitch)")
    print("=" * 60)
    print(f"{'Metric':<25} {'Teacher':<15} {'Student':<15}")
    print(f"{'BLEU score':<25} {teacher_result['bleu']:<15} {student_result['bleu']:<15}")
    print(f"{'Latency TB (ms)':<25} {teacher_result['avg_latency_ms']:<15} {student_result['avg_latency_ms']:<15}")
    print(f"{'Latency P95 (ms)':<25} {teacher_result['p95_latency_ms']:<15} {student_result['p95_latency_ms']:<15}")
    print(f"{'Số tham số (M)':<25} {teacher_result['num_params_millions']:<15} {student_result['num_params_millions']:<15}")

    speedup = teacher_result["avg_latency_ms"] / student_result["avg_latency_ms"]
    bleu_drop = teacher_result["bleu"] - student_result["bleu"]
    print(f"\n=> Student nhanh hơn {speedup:.2f}x, BLEU giảm {bleu_drop:.2f} điểm "
          f"(đổi lại tốc độ - đây chính là câu chuyện KD cần kể trong pitch)")

    with open("evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "teacher": teacher_result,
            "student": student_result,
            "speedup": round(speedup, 2),
            "bleu_drop": round(bleu_drop, 2),
        }, f, ensure_ascii=False, indent=2)
    print("\nĐã lưu evaluation_results.json")


if __name__ == "__main__":
    main()