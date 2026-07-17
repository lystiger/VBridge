# Audio fixture ground truth

All processed fixtures are human-recorded, 16 kHz mono PCM 16-bit WAV files. Original recordings remain under `tests/fixtures/audio_raw/`.

Regenerate the processed set with:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_audio_fixtures.py
```

## General fixtures

| File | Language | Spoken source transcript | Correct translation | Notes |
|---|---|---|---|---|
| `vi_clean_01.wav` | VI | Xin chào. | Hello. | Clean greeting; confirm punctuation. |
| `vi_clean_02.wav` | VI | Bạn khỏe không? | How are you? | Clean; confirm against recording. |
| `vi_clean_03.wav` | VI | Hôm nay trời đẹp nhỉ. | The weather is nice today. | Clean; confirm against recording. |
| `en_clean_01.wav` | EN | Hello. | Xin chào. | Clean greeting; confirm punctuation. |
| `en_clean_02.wav` | EN | How are you doing? | Bạn khỏe không? | Clean; confirm against recording. |
| `en_clean_03.wav` | EN | The weather is good today. | Hôm nay thời tiết đẹp. | Clean; confirm against recording. |
| `vi_noise_01.wav` | VI | Dậy đi. | Wake up. | Background noise; confirm against recording. |
| `en_noise_01.wav` | EN | Wake up. | Dậy đi. | Background noise; confirm against recording. |

## Business bilingual pairs

| Pair | File | Language | Spoken source transcript | Correct translation |
|---|---|---|---|---|
| 1 | `vi_business_01.wav` | VI | Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions. | Hello, I'm Minh, representing TechViet Solutions. |
| 1 | `en_business_01.wav` | EN | Hello, I'm Minh, representing TechViet Solutions. | Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions. |
| 2 | `vi_business_02.wav` | VI | Chúng tôi chuyên cung cấp giải pháp phần mềm cho ngành logistics. | We specialize in providing software solutions for the logistics industry. |
| 2 | `en_business_02.wav` | EN | We specialize in providing software solutions for the logistics industry. | Chúng tôi chuyên cung cấp giải pháp phần mềm cho ngành logistics. |

Business terms exercised: `TechViet Solutions` and `logistics`.

## Trailing-pause pair

| File | Language | Spoken source transcript | Correct translation | Notes |
|---|---|---|---|---|
| `vi_pause_01.wav` | VI | Dừng. | Pause. | Confirmed; natural trailing silence for VAD. |
| `en_pause_01.wav` | EN | Pause. | Dừng. | Confirmed; natural trailing silence for VAD. |

The pause transcripts and translations are human-confirmed. Their silence characteristics are measured during Sprint 02 VAD verification.
