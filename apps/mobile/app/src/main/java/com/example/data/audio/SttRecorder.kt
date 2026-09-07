package com.example.data.audio

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Base64
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * Records audio from the microphone and returns base64-encoded PCM data
 * for sending to the DASH backend's voice.stt WebSocket handler.
 *
 * Exposes a live [currentAmplitude] StateFlow (0..1000) that updates
 * ~16 times per second while recording, for driving waveform visuals.
 */
object SttRecorder {
    private const val TAG = "SttRecorder"
    private const val SAMPLE_RATE = 16000
    private const val CHANNEL = AudioFormat.CHANNEL_IN_MONO
    private const val ENCODING = AudioFormat.ENCODING_PCM_16BIT

    var isRecording = false
        private set

    private var audioRecord: AudioRecord? = null

    /** Live amplitude (0..1000) — updates ~16x/sec while recording, 0 when idle. */
    private val _currentAmplitude = MutableStateFlow(0)
    val currentAmplitude: StateFlow<Int> = _currentAmplitude.asStateFlow()

    private var amplitudeThread: Thread? = null

    fun start() {
        if (isRecording) return

        try {
            val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL, ENCODING)
            if (bufferSize == AudioRecord.ERROR || bufferSize == AudioRecord.ERROR_BAD_VALUE) {
                android.util.Log.e(TAG, "Invalid buffer size: $bufferSize")
                return
            }
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                CHANNEL,
                ENCODING,
                bufferSize * 2
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                android.util.Log.e(TAG, "AudioRecord failed to initialize")
                audioRecord?.release()
                audioRecord = null
                return
            }

            audioRecord?.startRecording()
            isRecording = true
            startAmplitudeMonitor()
            Log.i(TAG, "Recording started (16kHz mono PCM)")
        } catch (e: SecurityException) {
            Log.e(TAG, "Microphone permission denied", e)
            audioRecord = null
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            audioRecord?.release()
            audioRecord = null
        }
    }

    /** Background thread that reads 64-sample chunks and emits RMS amplitude. */
    private fun startAmplitudeMonitor() {
        amplitudeThread = Thread {
            val chunkSize = 64  // 4ms of 16kHz audio — ~250 reads/sec
            val buffer = ShortArray(chunkSize)
            try {
                while (isRecording) {
                    val record = audioRecord ?: break
                    val read = record.read(buffer, 0, chunkSize)
                    if (read > 0) {
                        var sum = 0L
                        for (i in 0 until read) {
                            sum += abs(buffer[i].toLong())
                        }
                        val avg = sum / read
                        // Scale to 0..1000 range (16-bit PCM max is 32767)
                        val amplitude = ((avg.toDouble() / 32767.0) * 1000.0).toInt().coerceIn(0, 1000)
                        _currentAmplitude.value = amplitude
                    }
                    Thread.sleep(4) // ~250fps update rate
                }
            } catch (_: InterruptedException) {
                // Normal stop
            } catch (e: Exception) {
                Log.e(TAG, "Amplitude monitor error", e)
            }
        }.also { it.isDaemon = true; it.start() }
    }

    suspend fun stop(maxDurationMs: Long = 30_000): String? = withContext(Dispatchers.IO) {
        if (!isRecording) return@withContext null

        isRecording = false
        _currentAmplitude.value = 0
        amplitudeThread?.interrupt()
        amplitudeThread = null

        val record = audioRecord ?: return@withContext null

        try {
            // Read all buffered audio
            val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL, ENCODING)
            val buffer = ByteArray(4096)
            val outputStream = ByteArrayOutputStream()
            val startTime = System.currentTimeMillis()

            while (isRecording || record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                val elapsed = System.currentTimeMillis() - startTime
                if (elapsed > maxDurationMs) break

                val bytesRead = record.read(buffer, 0, buffer.size)
                if (bytesRead > 0) {
                    outputStream.write(buffer, 0, bytesRead)
                } else if (bytesRead < 0) {
                    break
                }
            }

            record.stop()
            record.release()
            audioRecord = null

            val audioData = outputStream.toByteArray()
            if (audioData.isEmpty()) {
                Log.w(TAG, "No audio captured")
                return@withContext null
            }

            val base64 = Base64.encodeToString(audioData, Base64.NO_WRAP)
            Log.i(TAG, "Recording complete: ${audioData.size} bytes -> ${base64.length} base64 chars")
            base64
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording", e)
            record.release()
            audioRecord = null
            null
        }
    }

    fun cancel() {
        isRecording = false
        _currentAmplitude.value = 0
        amplitudeThread?.interrupt()
        amplitudeThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }
}
