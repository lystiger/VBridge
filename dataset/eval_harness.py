"""
VBridge Speech-to-Text and Translation Robustness Evaluation Harness.
Designed to systematically benchmark speech models under varying acoustic noise profiles.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import nltk
from jiwer import wer
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu

# Cấu hình logging chuyên nghiệp thay vì dùng hàm print thông thường
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("VBridgeEvaluator")


@dataclass
class EvaluatorConfig:
    """Cấu hình toàn cục cho hệ thống đánh giá (Harness Configuration)."""
    # CHẾ ĐỘ THỰC TẾ: Đã chuyển thành False để luôn nạp mô hình Whisper thật
    use_mock: bool = False  
    
    # Định vị đường dẫn động dựa trên vị trí của file script này (nằm trong thư mục 'dataset')
    script_dir: Path = Path(__file__).resolve().parent
    
    # Các thư mục dữ liệu đầu vào
    transcript_path: Path = Path(__file__).resolve().parent / "transcript" / "transcripts.json"
    clean_dir: Path = Path(__file__).resolve().parent / "audio" / "clean"
    noisy_dir: Path = Path(__file__).resolve().parent / "audio" / "noisy"
    
    environments: tuple[str, ...] = ("office", "cafe", "street")
    levels: tuple[str, ...] = ("level_light", "level_medium", "level_heavy")
    
    # Kết quả đầu ra sẽ được đẩy ra ngoài thư mục gốc của dự án để dễ quản lý
    report_path: Path = Path(__file__).resolve().parent.parent / "BENCHMARK_REPORT.md"
    results_path: Path = Path(__file__).resolve().parent.parent / "vbridge_robustness_results.json"


class TranslationService:
    """Lớp xử lý tích hợp mô hình AI dịch thuật (Inference Engine Wrapper)."""
    
    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock
        self.model = None
        if not self.use_mock:
            self._initialize_real_model()

    def _initialize_real_model(self) -> None:
        logger.info("Initializing Automatic Speech Recognition model (Whisper 'base')...")
        try:
            import torch
            import whisper
            
            # Tự động nhận diện GPU của dòng chip Apple Silicon (Mac M-series) để tăng tốc
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            logger.info(f"Hardware acceleration activated: Using {device.upper()}")
            
            # Nạp mô hình Whisper base thẳng vào GPU/CPU đã chọn
            self.model = whisper.load_model("base", device=device)
            logger.info("Whisper model loaded successfully into memory.")
        except ImportError:
            logger.error(
                "Dependency 'openai-whisper' or 'torch' not found. "
                "Please run: pip install openai-whisper torch. Falling back to Mock mode."
            )
            self.use_mock = True

    def translate(self, audio_path: Path, direction: str) -> str:
        """Thực hiện nhận dạng giọng nói và dịch thuật dựa trên cấu hình."""
        if self.use_mock:
            return self._mock_inference(audio_path, direction)
        return self._real_inference(audio_path, direction)

    def _mock_inference(self, audio_path: Path, direction: str) -> str:
        # Giả lập độ trễ xử lý của mô hình thực tế (latency simulation)
        time.sleep(0.01)
        path_str = str(audio_path)
        is_noisy = "noisy" in path_str
        is_heavy = "level_heavy" in path_str

        if direction == "vi2en":
            if is_heavy:
                return "Hello, I representative TechViet Solutions. We software for logistics."
            elif is_noisy:
                return "Hello, I am Minh representing TechViet Solutions. We provide software for logistics industry."
            return "Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry."
        else:
            if is_heavy:
                return "Chào buổi sáng tôi đại diện cho Aurora Tech Singapore."
            elif is_noisy:
                return "Chào buổi sáng tôi là Sarah tôi đại diện cho Aurora Tech Singapore."
            return "Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore."

    def _real_inference(self, audio_path: Path, direction: str) -> str:
        if not self.model:
            raise RuntimeError("Inference model has not been successfully initialized.")
        
        audio_str = str(audio_path)
        # Tiến hành dịch thuật End-to-End từ Audio sang Text
        if direction == "vi2en":
            result = self.model.transcribe(audio_str, task="translate")
        else:
            result = self.model.transcribe(audio_str, language="en")
        return result["text"].strip()


class MetricsCalculator:
    """Bộ tính toán chỉ số chất lượng dịch thuật và nhận dạng (Quality Metrics)."""

    @staticmethod
    def compute_bleu(ref: str, hyp: str) -> float:
        """Tính toán điểm BLEU score sử dụng smoothing function để tránh phân mảnh dữ liệu."""
        ref_tokens = nltk.word_tokenize(ref.lower())
        hyp_tokens = nltk.word_tokenize(hyp.lower())
        smoothing = SmoothingFunction().method1
        return float(sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothing))

    @staticmethod
    def compute_wer(ref: str, hyp: str) -> float:
        """Tính tỉ lệ lỗi từ (Word Error Rate)."""
        try:
            return float(wer(ref.lower(), hyp.lower()))
        except Exception:
            return 1.0

    @staticmethod
    def compute_glossary_accuracy(hyp: str, glossary: dict[str, str]) -> float:
        """Tính độ phủ chính xác của từ điển chuyên ngành trong câu dịch."""
        if not glossary:
            return 1.0
        hits = 0
        hyp_lower = hyp.lower()
        for src, tgt in glossary.items():
            if tgt.lower() in hyp_lower or src.lower() in hyp_lower:
                hits += 1
        return hits / len(glossary)


class RobustnessEvaluator:
    """Bộ khung điều phối toàn bộ tiến trình benchmark (Orchestration Engine)."""

    def __init__(self, config: EvaluatorConfig) -> None:
        self.config = config
        self.translator = TranslationService(use_mock=config.use_mock)
        self._ensure_nltk_resources()

    def _ensure_nltk_resources(self) -> None:
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)

    def load_ground_truth(self) -> dict[str, Any]:
        if not self.config.transcript_path.exists():
            raise FileNotFoundError(f"Critical Error: Ground truth file missing at {self.config.transcript_path}")
        with open(self.config.transcript_path, encoding="utf-8") as f:
            return json.load(f)

    def run_benchmark(self) -> list[dict[str, Any]]:
        """Quét qua toàn bộ ma trận dữ liệu và chấm điểm tự động."""
        ground_truth = self.load_ground_truth()
        results = []

        # Phần 1: Đánh giá tập dữ liệu Clean (Sạch)
        logger.info("Evaluating 'Clean' environment data...")
        for wav_name, info in ground_truth.items():
            audio_path = self.config.clean_dir / wav_name
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_path}")
                continue

            hyp_text = self.translator.translate(audio_path, info["direction"])
            results.append(self._build_result_record(wav_name, "Clean", "N/A", info, hyp_text))

        # Phần 2: Đánh giá tập dữ liệu Noisy (Ồn) qua ma trận môi trường
        logger.info("Evaluating multi-environment noise matrix...")
        for env in self.config.environments:
            for lvl in self.config.levels:
                logger.info(f"Processing Noise Profile: {env.upper()} | Level: {lvl.upper()}")
                for wav_name, info in ground_truth.items():
                    audio_path = self.config.noisy_dir / env / lvl / wav_name
                    if not audio_path.exists():
                        continue

                    hyp_text = self.translator.translate(audio_path, info["direction"])
                    results.append(self._build_result_record(wav_name, env, lvl, info, hyp_text))

        return results

    def _build_result_record(
        self, wav_name: str, env: str, lvl: str, info: dict[str, Any], hyp_text: str
    ) -> dict[str, Any]:
        bleu = MetricsCalculator.compute_bleu(info["ref"], hyp_text)
        wer_val = MetricsCalculator.compute_wer(info["ref"], hyp_text)
        gloss_acc = MetricsCalculator.compute_glossary_accuracy(hyp_text, info["glossary"])

        return {
            "wav_file": wav_name,
            "env": env,
            "level": lvl,
            "domain": info["domain"],
            "direction": info["direction"],
            "ref": info["ref"],
            "hyp": hyp_text,
            "bleu": bleu,
            "wer": wer_val,
            "glossary_acc": gloss_acc
        }


class ReportGenerator:
    """Bộ xuất dữ liệu báo cáo đa định dạng (Reporting Engine)."""

    @staticmethod
    def generate_markdown(results: list[dict[str, Any]], config: EvaluatorConfig) -> str:
        """Xây dựng báo cáo định dạng Markdown chi tiết."""
        stats: dict[tuple[str, str], dict[str, list[float]]] = {}
        for r in results:
            key = (r["env"], r["level"])
            if key not in stats:
                stats[key] = {"bleu": [], "wer": [], "glossary": []}
            stats[key]["bleu"].append(r["bleu"])
            stats[key]["wer"].append(r["wer"])
            stats[key]["glossary"].append(r["glossary_acc"])

        report = [
            "# 📊 BÁO CÁO ĐÁNH GIÁ ĐỘ BỀN BỈ MÔ HÌNH DỊCH THUẬT (VBRIDGE BENCHMARK)",
            f"*Ngày thực hiện: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*",
            f"*Chế độ thử nghiệm: {'Giả lập (Mock mode)' if config.use_mock else 'Mô hình AI Whisper Local'}*\n",
            "---",
            "\n## 📈 1. BẢNG TỔNG HỢP HIỆU NĂNG THEO MÔI TRƯỜNG & TIẾNG ỒN\n",
            "| Môi trường | Cấp độ nhiễu | Trung bình BLEU ↑ | Trung bình WER ↓ | Chính xác thuật ngữ ↑ | Trạng thái hệ thống |",
            "| :--- | :--- | :---: | :---: | :---: | :---: |"
        ]

        for (env, lvl), data in stats.items():
            avg_bleu = sum(data["bleu"]) / len(data["bleu"])
            avg_wer = sum(data["wer"]) / len(data["wer"])
            avg_glossary = sum(data["glossary"]) / len(data["glossary"])
            
            status = "🟢 Hoạt động tốt"
            if avg_wer > 0.45 or avg_bleu < 0.4:
                status = "🔴 Bị ảnh hưởng nặng"
            elif avg_wer > 0.25:
                status = "🟡 Suy giảm nhẹ"
                
            report.append(
                f"| **{env.upper()}** | {lvl} | {avg_bleu:.2%} | {avg_wer:.2%} | {avg_glossary:.2%} | {status} |"
            )

        report.extend([
            "\n---",
            "\n## 🔍 2. CHI TIẾT KẾT QUẢ TỪNG KỊCH BẢN THỬ NGHIỆM (TOP 10 BẢN SẠCH)\n",
            "| File Audio | Chiều dịch | Phân khúc | Bản gốc chuẩn (Reference) | Bản dịch của AI (Hypothesis) | Điểm BLEU | Điểm WER |",
            "| :--- | :---: | :---: | :--- | :--- | :---: | :---: |"
        ])

        for r in results:
            if r["env"] == "Clean":
                report.append(
                    f"| `{r['wav_file']}` | {r['direction']} | {r['domain']} | *{r['ref']}* | **{r['hyp']}** | {r['bleu']:.1%} | {r['wer']:.1%} |"
                )

        report.append("\n\n---\n*Báo cáo được tạo tự động bởi VBridge Robustness Testing Harness V1.0.*")
        return "\n".join(report)

    @classmethod
    def save(cls, results: list[dict[str, Any]], config: EvaluatorConfig) -> None:
        """Ghi báo cáo ra đĩa cứng."""
        # Lưu file JSON kết quả thô
        with open(config.results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        logger.info(f"Raw analysis metrics exported to: {config.results_path}")

        # Tạo và lưu báo cáo Markdown
        md_content = cls.generate_markdown(results, config)
        with open(config.report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Formatted benchmark report compiled at: {config.report_path}")


if __name__ == "__main__":
    logger.info("Starting VBridge Robustness Test Suite...")
    eval_config = EvaluatorConfig()
    evaluator = RobustnessEvaluator(eval_config)
    
    try:
        raw_results = evaluator.run_benchmark()
        ReportGenerator.save(raw_results, eval_config)
        logger.info("Evaluation process completed successfully.")
    except Exception as e:
        logger.exception(f"Fatal error occurred during execution: {e}")