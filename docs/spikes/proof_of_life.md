Here is the complete, self-contained Markdown file designed for you to download, save, or feed directly to your local AI model (such as Qwen-Coder or DeepSeek-R1) to begin building the native benchmark on your device.Save the content of the block below as ASR_Proof_Of_Life.md:Markdown# VBridge ASR Proof of Life (PoL) Blueprint

This document acts as the technical source-of-truth and implementation spec for the **ASR Proof of Life** benchmark on Android. The objective is to establish an unvarnished on-device transcription latency floor before writing the downstream translation, TTS, or UI synchronization pipelines.

---

## 1. Objectives & High-Risk Unknowns
Before proceeding with the full VBridge pipeline, we must answer a singular critical question:
> **Can our target phone transcribe speech on-device with a tolerable latency floor?**

*   **Model Selection:** We evaluate using a quantized **Whisper-Tiny (int8)** model (~75 MB).
*   **Hardware Baseline:** Xiaomi Note 14 (asymmetric 2 + 6 CPU core topology).
*   **Success Metric:** A Real-Time Factor (RTF) of **< 0.25** under sustained load (e.g., transcribing 5 seconds of raw audio in less than 1.25 seconds).

---

## 2. Project Layout Structure

Set up a clean, single-module native Android project in Android Studio using Kotlin and Gradle:

```text
VBridgePoL/
├── app/
│   ├── build.gradle.kts        # Project-level dependencies and ABI constraints
│   └── src/
│       └── main/
│           ├── AndroidManifest.xml
│           └── java/com/vbridge/pol/
│               ├── MainActivity.kt   # Simple triggering UI & output log
│               └── ASRPresenter.kt   # Hardware-optimized core profiler
└── settings.gradle.kts
3. Dependency ConfigurationThis configuration locks the build to 64-bit ARM architecture, strips duplicate R8 artifacts, and references the native sherpa-onnx library which bundles optimized ONNX Runtime binaries.app/build.gradle.ktsKotlinplugins {
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

        ndk {
            // Force 64-bit ARM to squeeze out maximum vector/NEON acceleration
            abiFilters.add("arm64-v8a")
        }
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
            // Workaround for Sherpa-ONNX metadata duplication issues
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
    
    // Sherpa-ONNX with bundled JNI runtime
    implementation("com.k2fsa.sherpa:sherpa-onnx:1.10.+")
}
4. Hardware-Optimized ProfilerThis module implements hardware-level optimizations specifically targeted at the asymmetric multi-core architecture of the Xiaomi Note 14.app/src/main/java/com/vbridge/pol/ASRPresenter.ktKotlinpackage com.vbridge.pol

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineWhisperModelConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class ASRPresenter(
    private val onTelemetry: (Telemetry) -> Unit
) {
    data class Telemetry(
        val text: String,
        val loadTimeMs: Long,
        val inferenceTimeMs: Long,
        val audioDurationMs: Long,
        val rtf: Float
    )

    private var recognizer: OfflineRecognizer? = null
    private var loadTimeMs: Long = 0

    /**
     * Initializes the model off the main UI thread.
     */
    suspend fun initModel(
        encoderPath: String,
        decoderPath: String,
        tokensPath: String
    ) = withContext(Dispatchers.IO) {
        val startTime = System.currentTimeMillis()

        val config = OfflineRecognizerConfig().apply {
            modelConfig = OfflineModelConfig().apply {
                whisper = OfflineWhisperModelConfig().apply {
                    encoder = encoderPath
                    decoder = decoderPath
                    language = "en" // Use "vi" to benchmark Vietnamese
                    task = "transcribe"
                }
                tokens = tokensPath
                
                // HARDWARE CRITICAL (Xiaomi Note 14 Optimization):
                // Locking to 2 threads ensures operations execute solely on 
                // the physical high-performance cores, preventing efficiency-core bottlenecks.
                numThreads = 2 
            }
        }

        recognizer = OfflineRecognizer(config)
        loadTimeMs = System.currentTimeMillis() - startTime
    }

    /**
     * Records exactly 5 seconds of 16 kHz Mono PCM audio.
     */
    @SuppressLint("MissingPermission")
    suspend fun recordBenchmarkAudio(): FloatArray = withContext(Dispatchers.IO) {
        val sampleRate = 16000
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        
        val audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            channelConfig,
            audioFormat,
            bufferSize
        )

        val sampleCount = sampleRate * 5 // 5 seconds of capture
        val shortBuffer = ShortArray(sampleCount)
        val floatBuffer = FloatArray(sampleCount)

        audioRecord.startRecording()
        
        var readSamples = 0
        while (readSamples < sampleCount) {
            val result = audioRecord.read(shortBuffer, readSamples, sampleCount - readSamples)
            if (result < 0) break
            readSamples += result
        }

        audioRecord.stop()
        audioRecord.release()

        // Normalize 16-bit signed PCM down to float32 [-1.0, 1.0] for the model
        for (i in 0 until sampleCount) {
            floatBuffer[i] = shortBuffer[i] / 32768.0f
        }

        floatBuffer
    }

    /**
     * Executes native model inference and profiles latency.
     */
    suspend fun runInference(samples: FloatArray) = withContext(Dispatchers.Default) {
        val activeRecognizer = recognizer ?: throw IllegalStateException("ASR Model not initialized")
        
        val inferenceStart = System.currentTimeMillis()
        
        val stream = activeRecognizer.createStream()
        stream.acceptWaveform(samples, 16000)
        activeRecognizer.decode(stream)
        val textResult = stream.text
        
        val inferenceEnd = System.currentTimeMillis()
        val inferenceTimeMs = inferenceEnd - inferenceStart
        val audioDurationMs = 5000L
        
        // RTF (Real-Time Factor) = Inference Time / Audio Duration
        val rtf = inferenceTimeMs.toFloat() / audioDurationMs.toFloat()

        stream.release()

        onTelemetry(
            Telemetry(
                text = textResult,
                loadTimeMs = loadTimeMs,
                inferenceTimeMs = inferenceTimeMs,
                audioDurationMs = audioDurationMs,
                rtf = rtf
            )
        )
    }
}
5. Execution Manifest & Model ProvisioningTo bypass early asset extraction overhead, bypass packaging inside the app. Download the pre-quantized files (e.g. from the official sherpa-onnx-whisper-tiny repository) and deploy them straight to your phone's external storage.Local ADB Deployment CommandsBash# 1. Verify that your Xiaomi Note 14 is recognized (Ensure USB debugging is enabled in Developer Options)
adb devices

# 2. Upload the Whisper-Tiny ONNX files directly to the target device directory
adb push whisper-tiny-encoder.int8.onnx /sdcard/Download/
adb push whisper-tiny-decoder.int8.onnx /sdcard/Download/
adb push whisper-tokens.txt /sdcard/Download/
Application Permission Requirements (AndroidManifest.xml)XML<manifest xmlns:android="[http://schemas.android.com/apk/res/xml](http://schemas.android.com/apk/res/xml)"
    package="com.vbridge.pol">

    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" 
        android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />

    <application
        android:requestLegacyExternalStorage="true"
        ... >
        <!-- Main activity definition goes here -->
    </application>
</manifest>
6. Real-World Decision Matrix for Xiaomi Note 14Evaluate your local log outputs against this matrix after completing 10 consecutive transcription runs under sustained load to track thermal behaviors:MetricPass (Proceed Natively)Marginally TolerableFail (Trigger Off-Ramp)Real-Time Factor (RTF)< 0.20 (Fast, consistent)0.21 - 0.35 (Mild delays)> 0.45 (Execution creates UX lag)Memory footprint< 150 MB150 - 300 MB> 400 MB (High OOM risk)CPU Heat / ThrottlingPerformance is flat over 10 runs< 15% speed drop in run #10System thermal-throttles earlyHyperOS CompatibilityBackground thread runs normallyOccasional thread freezingProcess killed immediately on lockscreen