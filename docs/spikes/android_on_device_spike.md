# Spike — Android On-Device ASR Proof-of-Life

**Branch:** `spike/android-on-device`
**Status:** open
**Owner:** MLOps (build/device) · AI eng (VI/EN transcript sanity)
**Time box:** 1 day. If it isn't answered in a day, the answer is "off-ramp."
**Target device:** Xiaomi/Redmi Note 14 — **confirm exact SoC before trusting numbers** (a Helio G99 / Dimensity 7025-class mid-ranger makes RTF < 0.25 optimistic; expect "marginal" and calibrate to the silicon). Testing on a mid-range phone is deliberate — if it works here, it works everywhere.

---

## 1. Why this spike exists

We've committed to a **fully on-device Android** demo: ASR → MT → TTS all run natively on the phone, no server. Before building any of that, we answer the **scariest single unknown**:

> Can the phone transcribe speech on-device at tolerable latency *at all*?

Everything else (MT, TTS, UI, the frozen contract, the native app) is downstream of this. This spike needs **zero help from the better machine** — it's a pure feasibility probe on the phone, which makes it the correct use of the current dead-end box's downtime.

## 2. Hypothesis

`sherpa-onnx` running **Whisper-tiny (int8 ONNX, ~75 MB)** transcribes a ~5 s utterance on the target device at **RTF < 0.30**, for both EN and VI, sustained over 10 runs without thermal collapse.

## 3. The gate — decide at end of day

Run **10 consecutive transcriptions under sustained load** and evaluate against a single continuous scale (this reconciles the two draft thresholds):

| Metric | Proceed (native on-device) | Marginal (reassess) | Off-ramp (thin client) |
| :--- | :--- | :--- | :--- |
| **RTF (tiny, sustained)** | **< 0.30** | 0.30 – 0.50 | **> 0.50** |
| Memory footprint | < 150 MB | 150 – 300 MB | > 400 MB (OOM risk) |
| Thermal over 10 runs | flat | < 15% slowdown by run 10 | throttles early |
| HyperOS background/lockscreen | thread runs | occasional freeze | process killed |

**Why the RTF gate is stricter than "just beat real-time":** tiny is the *floor*. The model VI accuracy actually needs (base/small/PhoWhisper) is **2–4× slower**. A tiny RTF of 0.30 leaves ~3× headroom before the real model hits real-time; a tiny RTF of 0.50 means the real model is already dead. Be strict on tiny *because* of the real model.

"Sane transcript" = recognizably the spoken sentence. **WER quality is not judged here** — that's the good-machine eval's job.

## 4. Off-ramp

If the gate fails, **on-device inference is dead** for now. Fall back to **phone-as-thin-client**: phone runs mic + UI, a mini-PC/laptop in the room runs the pipeline over LAN (still "on-device / no cloud" — the compute just isn't *in* the phone). `main`'s laptop web build stays the guaranteed fallback demo the entire time — **do not touch `main` during this spike.**

---

## 5. Implementation

Single-module Kotlin/Gradle app using **sherpa-onnx** (bundled ONNX Runtime + Whisper offline recognizer via Maven — no hand-built NDK).

### 5.1 Layout
```text
VBridgePoL/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── java/com/vbridge/pol/
│           ├── MainActivity.kt   # runtime permission + trigger + log
│           └── ASRPresenter.kt   # model load, capture, fixture load, profiler
└── settings.gradle.kts
```

### 5.2 `app/build.gradle.kts`
```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.vbridge.pol"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.vbridge.pol"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
        ndk { abiFilters.add("arm64-v8a") } // 64-bit ARM for NEON
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    packaging {
        resources {
            pickFirsts += "com/k2fsa/sherpa/onnx/BuildConfig.class"
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.9.0")
    implementation("com.k2fsa.sherpa:sherpa-onnx:1.10.+") // pin exact version before final
}
```

### 5.3 `AndroidManifest.xml` — FIXED
Fixes vs draft: correct `android` namespace; **no `MANAGE_EXTERNAL_STORAGE` / `requestLegacyExternalStorage`** (models load from the app-specific dir, which needs no storage permission); only `RECORD_AUDIO` remains.
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <application android:label="VBridge PoL" ...>
        <!-- MainActivity here -->
    </application>
</manifest>
```

### 5.4 Model + fixture provisioning — no special permission
`adb push` straight into the app-specific external dir (`getExternalFilesDir(null)` → `/sdcard/Android/data/com.vbridge.pol/files/`). No `MANAGE_EXTERNAL_STORAGE`, no user grant.
```bash
adb devices   # USB debugging on; confirm the Note 14 shows up

DST=/sdcard/Android/data/com.vbridge.pol/files
# Whisper-tiny int8 ONNX (from the official sherpa-onnx-whisper-tiny release)
adb push whisper-tiny-encoder.int8.onnx $DST/
adb push whisper-tiny-decoder.int8.onnx $DST/
adb push whisper-tokens.txt              $DST/
# Committed repo fixtures for a REPEATABLE, eval-comparable number
adb push tests/fixtures/audio_processed/en_clean_01.wav $DST/
adb push tests/fixtures/audio_processed/vi_clean_01.wav $DST/
adb push tests/fixtures/audio_processed/en_business_01.wav $DST/
adb push tests/fixtures/audio_processed/vi_business_01.wav $DST/
```

### 5.5 `MainActivity.kt` — runtime permission (was missing; benchmark returns silence without it)
```kotlin
package com.vbridge.pol

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 1)
        } else {
            startBenchmark()
        }
    }
    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, r: IntArray) {
        super.onRequestPermissionsResult(rc, p, r)
        if (rc == 1 && r.firstOrNull() == PackageManager.PERMISSION_GRANTED) startBenchmark()
    }
    private fun startBenchmark() { /* wire ASRPresenter: init → fixture runs → live run → log Telemetry */ }
}
```

### 5.6 `ASRPresenter.kt` — profiler (fixes: fixture path, true duration, configurable threads/lang)
```kotlin
package com.vbridge.pol

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.k2fsa.sherpa.onnx.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class ASRPresenter(private val onTelemetry: (Telemetry) -> Unit) {
    data class Telemetry(
        val label: String, val text: String,
        val loadTimeMs: Long, val inferenceTimeMs: Long,
        val audioDurationMs: Long, val rtf: Float,
    )

    private var recognizer: OfflineRecognizer? = null
    private var loadTimeMs: Long = 0

    // language configurable ("en" | "vi"); numThreads configurable — benchmark 2 vs 4.
    // NOTE: numThreads limits parallelism; it does NOT pin to big cores — the scheduler decides.
    suspend fun initModel(encoder: String, decoder: String, tokens: String,
                          language: String, numThreads: Int = 2) = withContext(Dispatchers.IO) {
        val start = System.currentTimeMillis()
        val config = OfflineRecognizerConfig().apply {
            modelConfig = OfflineModelConfig().apply {
                whisper = OfflineWhisperModelConfig().apply {
                    this.encoder = encoder; this.decoder = decoder
                    this.language = language; task = "transcribe"
                }
                this.tokens = tokens
                this.numThreads = numThreads
            }
        }
        recognizer = OfflineRecognizer(config)
        loadTimeMs = System.currentTimeMillis() - start
    }

    /** Repeatable path: decode a committed 16 kHz mono s16le WAV fixture. */
    suspend fun runFixture(label: String, wav: File) = withContext(Dispatchers.Default) {
        val samples = readPcm16Wav(wav)
        runInference(label, samples)
    }

    /** Secondary path: live 5 s mic capture. */
    @SuppressLint("MissingPermission")
    suspend fun runLive(label: String) = withContext(Dispatchers.Default) {
        runInference(label, recordSeconds(5))
    }

    private fun runInference(label: String, samples: FloatArray) {
        val rec = recognizer ?: error("ASR model not initialized")
        val durationMs = (samples.size * 1000L) / 16000L   // true duration, not hardcoded 5000
        val start = System.currentTimeMillis()
        val stream = rec.createStream()
        stream.acceptWaveform(samples, 16000)
        rec.decode(stream)
        val text = stream.text
        val inferMs = System.currentTimeMillis() - start
        stream.release()
        onTelemetry(Telemetry(label, text, loadTimeMs, inferMs, durationMs,
            inferMs.toFloat() / durationMs.toFloat()))
    }

    /** 44-byte header skip; PCM s16le mono → float32 [-1,1]. Matches our fixture format. */
    private fun readPcm16Wav(file: File): FloatArray {
        val bytes = file.readBytes()
        val n = (bytes.size - 44) / 2
        return FloatArray(n) { i ->
            val lo = bytes[44 + i * 2].toInt() and 0xFF
            val hi = bytes[44 + i * 2 + 1].toInt()
            ((hi shl 8) or lo).toShort() / 32768.0f
        }
    }

    @SuppressLint("MissingPermission")
    private fun recordSeconds(seconds: Int): FloatArray {
        val sr = 16000
        val minBuf = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.MIC, sr,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf)
        val total = sr * seconds
        val buf = ShortArray(total)
        rec.startRecording()
        var read = 0
        while (read < total) { val r = rec.read(buf, read, total - read); if (r < 0) break; read += r }
        rec.stop(); rec.release()
        return FloatArray(total) { buf[it] / 32768.0f }
    }
}
```

---

## 6. Results — fill in (EN **and** VI are both first-class)

| Device / SoC | Model | Threads | Input | Audio ms | Load ms | Infer ms | RTF | Transcript sane? |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| | tiny-int8 | 2 | en_clean_01 | | | | | |
| | tiny-int8 | 2 | vi_clean_01 | | | | | |
| | tiny-int8 | 4 | en_clean_01 | | | | | |
| | tiny-int8 | 4 | vi_clean_01 | | | | | |
| | tiny-int8 | best | live EN | | | | | |
| | tiny-int8 | best | live VI | | | | | |

Also record: peak memory, RTF drift across the 10-run loop (thermal), and whether the thread survives lockscreen (HyperOS).

## 7. Explicitly NOT in this spike
MT and TTS on device · model selection / accuracy tuning (good-machine eval lab) · the frozen cross-implementation contract · **any change to `main`**.

## 8. If the gate passes → next
1. Freeze the stage contract (ASR/MT/TTS/VAD interfaces + event protocol) from the Python schemas as the language-agnostic source of truth.
2. Add MT (**MarianMT/OPUS-MT via ONNX Runtime Mobile** — mobile-friendlier than NLLB) and TTS (Piper, vi_VN + en) to the on-device chain.
3. Keep the Python backend as the reference impl + eval lab on the good machine; the phone is a parallel native impl of the same contract.

## 9. Standing caveats
- **Tiny latency ≠ the VI model you'll ship.** The real VI-accuracy model is 2–4× slower; a passing tiny RTF proves *capability*, not the production number.
- **Confirm the SoC.** The whole decision is device-specific; a mid-range MediaTek changes what "pass" looks like.
- **HyperOS will fight you.** Background-execution / lockscreen survival is a real risk for a live meeting app — treat it as a gate metric, not an afterthought.
