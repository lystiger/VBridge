import re
import time
from pathlib import Path

import pandas as pd
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSeq2SeqLM

MODEL_DIR = Path("vbridge_model")
DIALOGUE_MD = Path("dataset/dialogues/test_dialogues.md")

LANG_CODE_MAP = {"vi": "vie_Latn", "en": "eng_Latn"}


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


def load_dialogues() -> list[dict]:
    """Mỗi đoạn: câu nguồn (S_SRC) gộp lại + câu đáp án dịch (S_REF) gộp lại."""
    text = DIALOGUE_MD.read_text(encoding="utf-8-sig")
    blocks = text.split("---")
    dialogues = []
    for block in blocks:
        id_match = re.search(r"Đoạn\s*(\d+)", block)
        lang_match = re.search(r"LANG:\s*(\w+)", block)
        if not (id_match and lang_match):
            continue
        direction = lang_match.group(1)  # vi2en hoặc en2vi
        src_lang, tgt_lang = ("vi", "en") if direction == "vi2en" else ("en", "vi")
        srcs = re.findall(r"S\d+_SRC:\s*(.+)", block)
        refs = re.findall(r"S\d+_REF:\s*(.+)", block)
        # Ghép từng câu riêng để mô hình dịch chuẩn ngữ cảnh ngắn
        for src, ref in zip(srcs, refs):
            dialogues.append({
                "id": int(id_match.group(1)), "src_lang": src_lang, "tgt_lang": tgt_lang,
                "src_text": src.strip(), "ref_text": ref.strip(),
            })
    return dialogues


def translate(model, tokenizer, text: str, src_lang: str, tgt_lang: str) -> tuple:
    # Set ngôn ngữ nguồn nếu tokenizer có hỗ trợ thuộc tính src_lang
    if hasattr(tokenizer, "src_lang"):
        tokenizer.src_lang = LANG_CODE_MAP.get(src_lang, src_lang)

    inputs = tokenizer(text, return_tensors="pt")

    gen_kwargs = {}
    
    # Lấy mã ngôn ngữ đích (ví dụ: vie_Latn)
    target_code = LANG_CODE_MAP.get(tgt_lang, tgt_lang)
    
    # Tìm Token ID tương ứng từ bộ từ vựng một cách an toàn
    target_token_id = None
    if hasattr(tokenizer, "lang_code_to_id") and tokenizer.lang_code_to_id:
        if target_code in tokenizer.lang_code_to_id:
            target_token_id = tokenizer.lang_code_to_id[target_code]
            
    # Hỗ trợ cơ chế fallback nếu không có lang_code_to_id (Đoạn sửa đổi cốt lõi)
    if target_token_id is None:
        target_token_id = tokenizer.convert_tokens_to_ids(target_code)

    # Ép buộc mô hình sinh ra ngôn ngữ đích chuẩn xác (Tránh loạn ngôn ngữ)
    if target_token_id is not None and target_token_id != tokenizer.unk_token_id:
        gen_kwargs["forced_bos_token_id"] = target_token_id

    t0 = time.time()
    output_ids = model.generate(**inputs, **gen_kwargs, max_new_tokens=128)
    latency = time.time() - t0

    output_text = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
    return output_text, latency


def main():
    print("Đang tải model + tokenizer...")
    model = ORTModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)

    dialogues = load_dialogues()
    print(f"Tìm thấy {len(dialogues)} câu cần dịch\n")

    rows = []
    for d in dialogues:
        hyp_text, latency = translate(model, tokenizer, d["src_text"], d["src_lang"], d["tgt_lang"])
        wer = word_error_rate(hyp_text, d["ref_text"])
        accuracy = max(0.0, 1 - wer) * 100

        rows.append({
            "dialogue_id": d["id"], "direction": f"{d['src_lang']}2{d['tgt_lang']}",
            "accuracy_pct": round(accuracy, 1), "latency_s": round(latency, 3),
        })
        print(f"[Đoạn {d['id']:02d}, {d['src_lang']}->{d['tgt_lang']}] "
              f"accuracy={accuracy:.1f}%  latency={latency:.2f}s")
        print(f"   Nguồn:  {d['src_text']}")
        print(f"   Đáp án: {d['ref_text']}")
        print(f"   Model:  {hyp_text}\n")

    df = pd.DataFrame(rows)
    df.to_csv("vbridge_mt_evaluation.csv", index=False)

    print("=" * 60)
    print(f"ĐỘ CHÍNH XÁC TRUNG BÌNH: {df['accuracy_pct'].mean():.1f}%")
    print(f"ĐỘ TRỄ TRUNG BÌNH: {df['latency_s'].mean():.2f}s")
    print("\nTheo chiều dịch:")
    print(df.groupby("direction")[["accuracy_pct", "latency_s"]].mean().round(2).to_string())
    print("\nĐã lưu vbridge_mt_evaluation.csv")

if __name__ == "__main__":
    main()