package com.example.data.audio

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Lightweight wake word detector using amplitude-based Voice Activity Detection (VAD).
 *
 * Continuously monitors microphone amplitude at low power. When voice is detected
 * (amplitude above threshold for consecutive frames), signals the caller to start
 * full STT recording. Backend then checks for "Hey DASH" patterns in the transcript.
 *
 * Battery-friendly: uses short audio windows and sleeps between checks.
 */
object WakeWordDetector {
    private const val TAG = "WakeWordDetector"
    private const val SAMPLE_RATE = 16000
    private const val CHANNEL = AudioFormat.CHANNEL_IN_MONO
    private const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
    private const val PREFS_NAME = "dash_wake_word"
    private const val KEY_PHRASE = "wake_phrase"
    private const val KEY_ENABLED = "wake_enabled"
    private const val DEFAULT_PHRASE = "Hey DASH" 

    // Amplitude thresholds
    private const val VOICE_AMPLITUDE_THRESHOLD = 800   // Min amplitude to consider as voice
    private const val CONSECUTIVE_FRAMES_NEEDED = 3     // Voice frames needed to trigger
    private const val SILENCE_FRAMES_TO_RESET = 5       // Silence frames to reset detection
    private const val FRAME_DURATION_MS = 200           // Each analysis frame duration
    private const val COOLDOWN_MS = 5000L               // Cooldown after wake word triggered

    private var isRunning = false
    private var detectorJob: Job? = null
    private var audioRecord: AudioRecord? = null

    private val _isWakeWordEnabled = MutableStateFlow(false)
    val isWakeWordEnabled: StateFlow<Boolean> = _isWakeWordEnabled.asStateFlow()

    private val _customPhrase = MutableStateFlow(DEFAULT_PHRASE)
    val customPhrase: StateFlow<String> = _customPhrase.asStateFlow()

    private var prefs: android.content.SharedPreferences? = null

    fun init(context: android.content.Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
        _isWakeWordEnabled.value = prefs?.getBoolean(KEY_ENABLED, false) ?: false
        _customPhrase.value = prefs?.getString(KEY_PHRASE, DEFAULT_PHRASE) ?: DEFAULT_PHRASE
    }

    fun setWakeWordEnabled(enabled: Boolean) {
        _isWakeWordEnabled.value = enabled
        prefs?.edit()?.putBoolean(KEY_ENABLED, enabled)?.apply()
    }

    fun setCustomPhrase(phrase: String) {
        val trimmed = phrase.trim().ifEmpty { DEFAULT_PHRASE }
        _customPhrase.value = trimmed
        prefs?.edit()?.putString(KEY_PHRASE, trimmed)?.apply()
    }

    private val _isDetecting = MutableStateFlow(false)
    val isDetecting: StateFlow<Boolean> = _isDetecting.asStateFlow()

    private val _wakeWordDetected = MutableStateFlow(false)
    val wakeWordDetected: StateFlow<Boolean> = _wakeWordDetected.asStateFlow()

    // Callback invoked when wake word is detected
    private var onWakeWord: (() -> Unit)? = null

    fun startDetection(scope: CoroutineScope, onWakeWord: () -> Unit) {
        if (isRunning || !_isWakeWordEnabled.value) return

        this.onWakeWord = onWakeWord
        isRunning = true
        _isDetecting.value = true

        detectorJob = scope.launch(Dispatchers.IO) {
            Log.i(TAG, "Wake word detection started")
            var consecutiveVoiceFrames = 0
            var consecutiveSilenceFrames = 0
            var lastTriggerTime = 0L

            try {
                val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL, ENCODING)
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    CHANNEL,
                    ENCODING,
                    bufferSize
                )

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    Log.e(TAG, "AudioRecord failed to initialize")
                    isRunning = false
                    _isDetecting.value = false
                    return@launch
                }

                audioRecord?.startRecording()
                Log.i(TAG, "Microphone opened for wake word detection")

                val readSize = (SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2 // 16-bit = 2 bytes
                val buffer = ShortArray(readSize)

                while (isRunning && isActive) {
                    if (!_isWakeWordEnabled.value) {
                        delay(1000)
                        continue
                    }

                    val read = audioRecord?.read(buffer, 0, readSize) ?: 0
                    if (read <= 0) {
                        delay(100)
                        continue
                    }

                    // Calculate RMS amplitude
                    var sum = 0L
                    for (i in 0 until read step 2) {
                        val sample = buffer[i].toLong()
                        sum += sample * sample
                    }
                    val rms = kotlin.math.sqrt(sum.toDouble() / (read / 2)).toInt()

                    if (rms > VOICE_AMPLITUDE_THRESHOLD) {
                        consecutiveVoiceFrames++
                        consecutiveSilenceFrames = 0

                        if (consecutiveVoiceFrames >= CONSECUTIVE_FRAMES_NEEDED) {
                            val now = System.currentTimeMillis()
                            if (now - lastTriggerTime > COOLDOWN_MS) {
                                lastTriggerTime = now
                                Log.i(TAG, "Wake word detected (amplitude: $rms)")
                                _wakeWordDetected.value = true

                                withContext(Dispatchers.Main) {
                                    onWakeWord()
                                }

                                // Reset after trigger
                                consecutiveVoiceFrames = 0
                                delay(COOLDOWN_MS)
                                _wakeWordDetected.value = false
                            }
                        }
                    } else {
                        consecutiveSilenceFrames++
                        if (consecutiveSilenceFrames >= SILENCE_FRAMES_TO_RESET) {
                            consecutiveVoiceFrames = 0
                        }
                    }

                    // Sleep to save battery between frames
                    delay(50)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Wake word detection error: ${e.message}")
            } finally {
                stopRecording()
                isRunning = false
                _isDetecting.value = false
                Log.i(TAG, "Wake word detection stopped")
            }
        }
    }

    fun stopDetection() {
        isRunning = false
        detectorJob?.cancel()
        detectorJob = null
        stopRecording()
        _isDetecting.value = false
        _wakeWordDetected.value = false
        Log.i(TAG, "Wake word detection stopped")
    }

    private fun stopRecording() {
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }
}
