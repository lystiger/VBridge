

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch

MODEL_NAME = "facebook/nllb-200-distilled-600M"

# Mã ngôn ngữ NLLB (khác với mã ISO thông thường)
LANG_CODES = {
    "vi": "vie_Latn",
    "en": "eng_Latn",
}

class Translator:
    def __init__(self, model_name: str = MODEL_NAME, device: str = "cpu"):
        print(f"[MT] Loading translation model '{model_name}'...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)
        self.device = device
        print("[MT] Model loaded.")

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """
        src_lang, tgt_lang: "vi" hoặc "en"
        """
        self.tokenizer.src_lang = LANG_CODES[src_lang]
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(LANG_CODES[tgt_lang])
        generated = self.model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=256,
            num_beams=4,                  # beam search thay vì greedy - giảm lặp vòng đáng kể
            no_repeat_ngram_size=3,        # cấm lặp lại cụm 3 từ trở lên (chặn "wears, wears, wears...")
            repetition_penalty=1.3,        # phạt token đã xuất hiện, khuyến khích sinh từ mới
            early_stopping=True,
        )
        result = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        return result


if __name__ == "__main__":
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Test standalone - device: {device}")
    mt = Translator(device=device)
    print(mt.translate("Chúng tôi rất vui được hợp tác với quý công ty.", "vi", "en"))
    print(mt.translate("We are excited to explore this partnership further.", "en", "vi"))