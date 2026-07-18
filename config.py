"""
Config tập trung — đổi model, path, hyperparameter chỉ cần sửa ở đây,
không cần đào code trong các file khác. (Theo đúng góp ý #6 của bạn cậu.)
"""

# --- Models ---
# LƯU Ý QUAN TRỌNG: Meta KHÔNG có bản NLLB nào nhỏ hơn 600M (không tồn tại "350M").
# Các bản chính thức: distilled-600M (nhỏ nhất), distilled-1.3B, 1.3B, 3.3B.
# Vì vậy teacher và student dùng CÙNG kiến trúc 600M - "distillation" ở đây là
# CHUYÊN BIỆT HÓA DOMAIN (student học riêng phong cách hội thoại kinh doanh qua
# pseudo-label của teacher), KHÔNG PHẢI nén kiến trúc nhỏ lại.
# Việc giảm kích thước/tốc độ THẬT SỰ đến từ bước quantization INT8 khi export
# ONNX (xem edge_deploy/export_onnx.py) - đó mới là đòn bẩy nén cho edge deployment.
TEACHER_MODEL = "facebook/nllb-200-distilled-600M"
STUDENT_MODEL_INIT = "facebook/nllb-200-distilled-600M"  # cùng size, fine-tune chuyên biệt domain

LANG_CODES = {"vi": "vie_Latn", "en": "eng_Latn"}

# --- Data ---
RAW_DATA_PATH = "data/parallel_vi_en.tsv"   # format: câu_vi \t câu_en (mỗi dòng 1 cặp)
PSEUDO_LABELED_PATH = "data/pseudo_labeled.jsonl"  # output sau khi teacher tạo pseudo-label
TRAIN_SPLIT_RATIO = 0.85
VAL_SPLIT_RATIO = 0.10
TEST_SPLIT_RATIO = 0.05   # giữ riêng, KHÔNG bao giờ dùng để train hay validate trong lúc train
MAX_TRAIN_SAMPLES = 300000   # cấu hình tập trung số lượng câu dùng để train/demo (đổi thành 100000 nếu thử nhanh)

RANDOM_SEED = 42

# --- Training ---
OUTPUT_DIR = "student_model_checkpoint"
BATCH_SIZE = 8          # RTX 4060 8GB - bắt đầu conservative, tăng dần nếu còn VRAM
GRAD_ACCUM_STEPS = 4    # effective batch size = BATCH_SIZE * GRAD_ACCUM_STEPS = 32
LEARNING_RATE = 3e-5
NUM_EPOCHS = 3           # 48h không cho phép train nhiều epoch, 2-3 là hợp lý
MAX_SEQ_LENGTH = 128      # câu hội thoại họp thường không quá dài
FP16 = True               # bắt buộc bật để tiết kiệm VRAM trên 8GB
SAVE_STEPS = 200           # lưu checkpoint thường xuyên - phòng hết giờ giữa chừng
EVAL_STEPS = 200

# --- Distillation generation (bước tạo pseudo-label từ teacher) ---
TEACHER_GEN_BATCH_SIZE = 16
TEACHER_NUM_BEAMS = 1      # beam search cho chất lượng pseudo-label tốt hơn (chậm hơn greedy)

# ĐỒNG BỘ HOÀN TOÀN: Tự động lấy theo số lượng câu của tập train để tránh lệch data giữa các bước
MAX_SOURCE_SENTENCES = MAX_TRAIN_SAMPLES