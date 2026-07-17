# Audio fixtures — ground truth

Test clips for ASR/MT verification and the eval harness. All clips: **16 kHz, mono, WAV (PCM s16le)**, scripted non-sensitive business sentences in the recorder's own voice. Safe to commit.

Convert anything that isn't already 16k mono:
`ffmpeg -i in.wav -ar 16000 -ac 1 -c:a pcm_s16le out.wav`

| File | Lang | Spoken (source transcript) | Correct translation | Notes |
|---|---|---|---|---|
| `vi_clean_01.wav` | VI | _<what you said in Vietnamese>_ | _<correct English>_ | clean, contains a deal term |
| `en_clean_01.wav` | EN | _<what you said in English>_ | _<correct Vietnamese>_ | clean, contains a deal term |
| `vi_pause_01.wav` | VI | _<Vietnamese sentence>_ | _<correct English>_ | trailing silence for VAD/T6 |
| `en_pause_01.wav` | EN | _<English sentence>_ | _<correct Vietnamese>_ | trailing silence for VAD/T6 |
| `vi_noise_01.wav` | VI | _<Vietnamese sentence>_ | _<correct English>_ | optional, light background noise |
| `en_noise_01.wav` | EN | _<English sentence>_ | _<correct Vietnamese>_ | optional, light background noise |

The eval harness scores ASR output against the "Spoken" column and MT output against the "Correct translation" column. Keep transcripts exact — they are the ground truth.
