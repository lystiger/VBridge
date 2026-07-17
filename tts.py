

import os
import tempfile
from gtts import gTTS

LANG_MAP = {"vi": "vi", "en": "en"}


class TTSEngine:
    def __init__(self, offline: bool = False):
        self.offline = offline
        if offline:
            # Coqui TTS - chạy hoàn toàn local, không cần internet
            from TTS.api import TTS as CoquiTTS
            # model đa ngôn ngữ, có hỗ trợ tiếng Việt tùy phiên bản - kiểm tra model list trước khi dùng
            self.engine = CoquiTTS(model_name="tts_models/multilingual/multi-dataset/your_tts")
        else:
            self.engine = None  # gTTS không cần load model trước

    def speak_to_file(self, text: str, lang: str, out_path: str = None) -> str:
        """
        Trả về đường dẫn file audio (mp3/wav) đã tạo.
        """
        if out_path is None:
            out_path = tempfile.mktemp(suffix=".mp3" if not self.offline else ".wav")

        if self.offline:
            self.engine.tts_to_file(text=text, file_path=out_path, language=LANG_MAP[lang])
        else:
            tts = gTTS(text=text, lang=LANG_MAP[lang])
            tts.save(out_path)

        return out_path


if __name__ == "__main__":
    tts = TTSEngine(offline=False)
    path = tts.speak_to_file("Xin chào, rất vui được gặp quý vị.", "vi")
    print("Saved to:", path)