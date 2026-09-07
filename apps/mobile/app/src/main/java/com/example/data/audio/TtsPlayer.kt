package com.example.data.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Base64
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

/**
 * Plays TTS audio received from the DASH backend as base64-encoded WAV.
 * Emits currentAmplitude (0..1000) during playback for orb animation.
 */
object TtsPlayer {
    private const val TAG = "TtsPlayer"
    private var currentTrack: AudioTrack? = null
    var isSpeaking: Boolean = false
        private set
    var onComplete: (() -> Unit)? = null

    /** Live amplitude (0..1000) during TTS playback, 0 when idle. */
    private val _currentAmplitude = MutableStateFlow(0)
    val currentAmplitude: StateFlow<Int> = _currentAmplitude.asStateFlow()

    /** Background thread that samples PCM data to emit amplitude. */
    private var amplitudeThread: Thread? = null

    /**
     * Play base64-encoded audio (WAV format from Piper TTS).
     * Runs on IO dispatcher to avoid blocking the main thread.
     */
    suspend fun play(base64Audio: String) = withContext(Dispatchers.IO) {
        try {
            stop() // Stop any currently playing audio

            val audioBytes = Base64.decode(base64Audio, Base64.DEFAULT)
            if (audioBytes.isEmpty()) {
                Log.w(TAG, "Empty audio data")
                return@withContext
            }

            // Parse WAV header to get format info
            val pcmData = parseWav(audioBytes)
            if (pcmData.isEmpty()) {
                Log.w(TAG, "No PCM data found in WAV")
                return@withContext
            }

            val sampleRate = 22050 // Piper default
            val channelConfig = AudioFormat.CHANNEL_OUT_MONO
            val audioFormat = AudioFormat.ENCODING_PCM_16BIT
            val bufferSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, audioFormat)

            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(sampleRate)
                        .setChannelMask(channelConfig)
                        .setEncoding(audioFormat)
                        .build()
                )
                .setBufferSizeInBytes(maxOf(bufferSize, pcmData.size))
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()

            currentTrack = track
            isSpeaking = true

            // Start amplitude monitoring from PCM data
            startAmplitudeEmission(pcmData, sampleRate)

            track.write(pcmData, 0, pcmData.size)
            track.play()

            // Wait for playback to finish
            val durationMs = (pcmData.size.toLong() * 1000) / (sampleRate * 2) // 16-bit mono
            Thread.sleep(durationMs.coerceAtMost(30_000)) // Max 30s safety

            stopAmplitudeEmission()
            _currentAmplitude.value = 0
            isSpeaking = false
            Log.i(TAG, "TTS playback complete (${durationMs}ms)")
            // Notify conversation mode to auto-listen
            val callback = onComplete
            onComplete = null
            callback?.invoke()
        } catch (e: Exception) {
            Log.e(TAG, "TTS playback failed", e)
            stopAmplitudeEmission()
            _currentAmplitude.value = 0
            isSpeaking = false
        }
    }

    fun stop() {
        try {
            currentTrack?.stop()
            currentTrack?.release()
        } catch (_: Exception) {}
        currentTrack = null
        isSpeaking = false
        stopAmplitudeEmission()
        _currentAmplitude.value = 0
    }

    /**
     * Emit amplitude from PCM data at ~30fps for smooth orb animation.
     * Samples non-overlapping 512-sample windows from the 16-bit mono PCM.
     */
    private fun startAmplitudeEmission(pcmData: ByteArray, sampleRate: Int) {
        stopAmplitudeEmission()
        amplitudeThread = Thread {
            try {
                val chunkSamples = 512
                val chunkBytes = chunkSamples * 2 // 16-bit = 2 bytes per sample
                val totalSamples = pcmData.size / 2
                val totalChunks = (totalSamples / chunkSamples).coerceAtLeast(1)
                val frameInterval = 33L // ~30fps

                for (chunk in 0 until totalChunks) {
                    val byteOffset = chunk * chunkBytes
                    if (byteOffset + chunkBytes > pcmData.size) break

                    // Compute RMS amplitude from this chunk
                    var sum = 0L
                    for (i in 0 until chunkSamples) {
                        val sampleIdx = byteOffset + i * 2
                        if (sampleIdx + 1 >= pcmData.size) break
                        val sample = (pcmData[sampleIdx].toInt() and 0xFF) or
                                (pcmData[sampleIdx + 1].toInt() shl 8)
                        sum += sample.toLong() * sample.toLong()
                    }
                    val rms = kotlin.math.sqrt(sum.toDouble() / chunkSamples).toInt()
                    val amplitude = ((rms.toDouble() / 32767.0) * 1000.0).toInt()
                        .coerceIn(0, 1000)
                    _currentAmplitude.value = amplitude

                    Thread.sleep(frameInterval)
                }
            } catch (e: InterruptedException) {
                // Thread interrupted — normal during stop
            } catch (e: Exception) {
                Log.e(TAG, "Amplitude emission error", e)
            }
        }
        amplitudeThread?.isDaemon = true
        amplitudeThread?.start()
    }

    private fun stopAmplitudeEmission() {
        amplitudeThread?.interrupt()
        amplitudeThread = null
    }

    /**
     * Parse WAV file and extract raw PCM data.
     * Handles standard WAV format from Piper TTS.
     */
    private fun parseWav(data: ByteArray): ByteArray {
        if (data.size < 44) return data // Too short for WAV header, treat as raw PCM

        // Check for RIFF header
        val header = String(data, 0, 4)
        if (header != "RIFF") return data // Not WAV, treat as raw PCM

        // Find "data" chunk
        var offset = 12 // Skip RIFF header
        while (offset < data.size - 8) {
            val chunkId = String(data, offset, 4)
            val chunkSize = readInt32LE(data, offset + 4)

            if (chunkId == "data") {
                return data.copyOfRange(offset + 8, offset + 8 + chunkSize)
            }
            offset += 8 + chunkSize
        }
        return data.copyOfRange(44, data.size) // Fallback: skip 44-byte WAV header
    }

    private fun readInt32LE(data: ByteArray, offset: Int): Int {
        return (data[offset].toInt() and 0xFF) or
                ((data[offset + 1].toInt() and 0xFF) shl 8) or
                ((data[offset + 2].toInt() and 0xFF) shl 16) or
                ((data[offset + 3].toInt() and 0xFF) shl 24)
    }
}
