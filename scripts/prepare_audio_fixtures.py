"""Normalize human-recorded source clips into Sprint 02 WAV fixtures."""

from pathlib import Path

import av
import numpy as np
import soundfile as sf
from av.audio.resampler import AudioResampler

SOURCE_DIR = Path("tests/fixtures/audio_raw")
OUTPUT_DIR = Path("tests/fixtures/audio_processed")
SAMPLE_RATE = 16_000

FIXTURE_MAP = {
    "eng/hello.m4a": "en_clean_01.wav",
    "eng/howareudoing.m4a": "en_clean_02.wav",
    "eng/theweatherisgoodtoday.m4a": "en_clean_03.wav",
    "engwithnoise/wakeup(withnoise).m4a": "en_noise_01.wav",
    "vn/xinchao.m4a": "vi_clean_01.wav",
    "vn/bankhoekhong.m4a": "vi_clean_02.wav",
    "vn/homnaytroidepnhi.m4a": "vi_clean_03.wav",
    "vnwithnoise/daydi(withnoise).m4a": "vi_noise_01.wav",
    "eng/HelloImMinhrepresentingTechVietSolutions..mp3": "en_business_01.wav",
    "eng/Wespecializeinprovidingsoftwaresolutionsforthelogisticsindustry.mp3": (
        "en_business_02.wav"
    ),
    "vn/Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions.mp3": ("vi_business_01.wav"),
    "vn/Chúng tôi chuyên cung cấp giải pháp phần mềm cho ngành logistics.mp3": (
        "vi_business_02.wav"
    ),
    "eng/engpause.m4a": "en_pause_01.wav",
    "vn/vnpause4a.m4a": "vi_pause_01.wav",
}


def decode_mono_pcm(source: Path) -> np.ndarray:
    resampler = AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    with av.open(str(source)) as container:
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                chunks.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            chunks.append(converted.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError(f"No audio frames decoded from {source}")
    return np.concatenate(chunks)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for source_name, output_name in FIXTURE_MAP.items():
        source = SOURCE_DIR / source_name
        if not source.exists():
            print(f"SKIP missing: {source}")
            continue
        output = OUTPUT_DIR / output_name
        samples = decode_mono_pcm(source)
        sf.write(output, samples, SAMPLE_RATE, subtype="PCM_16")
        print(f"WROTE {output} ({len(samples) / SAMPLE_RATE:.2f}s)")


if __name__ == "__main__":
    main()
