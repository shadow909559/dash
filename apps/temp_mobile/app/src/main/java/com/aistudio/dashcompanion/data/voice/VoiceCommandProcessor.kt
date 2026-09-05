package com.aistudio.dashcompanion.data.voice

import android.content.Context
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import com.aistudio.dashcompanion.data.command.CommandExecutionManager
import com.aistudio.dashcompanion.features.voice.VoiceStateManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Voice Command Processor
 * Handles speech recognition and command parsing for desktop control
 */
object VoiceCommandProcessor {
    private const val TAG = "VoiceCommand"
    
    enum class VoiceState {
        Idle,
        Listening,
        Processing,
        Executing,
        Speaking,
        Error
    }
    
    data class VoiceCommand(
        val originalText: String,
        val parsedCommand: String?,
        val parameters: Map<String, String>,
        val confidence: Float
    )
    
    private val _voiceState = MutableStateFlow<VoiceState>(VoiceState.Idle)
    val voiceState: StateFlow<VoiceState> = _voiceState.asStateFlow()
    
    private val _recognizedText = MutableStateFlow<String>("")
    val recognizedText: StateFlow<String> = _recognizedText.asStateFlow()
    
    private val _currentCommand = MutableStateFlow<VoiceCommand?>(null)
    val currentCommand: StateFlow<VoiceCommand?> = _currentCommand.asStateFlow()
    
    private var speechRecognizer: SpeechRecognizer? = null
    private var context: Context? = null
    
    // Command patterns
    private val commandPatterns = mapOf(
        "open" to listOf("open", "launch", "start", "run"),
        "volume" to listOf("volume", "sound", "audio"),
        "brightness" to listOf("brightness", "screen", "display"),
        "media" to listOf("play", "pause", "stop", "next", "previous", "skip"),
        "lock" to listOf("lock", "lock desktop", "lock computer"),
        "system" to listOf("status", "what's", "tell me", "information"),
        "close" to listOf("close", "quit", "exit"),
        "minimize" to listOf("minimize", "hide"),
        "maximize" to listOf("maximize", "fullscreen")
    )
    
    /**
     * Initialize with context
     */
    fun setContext(context: Context) {
        this.context = context
        this.speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
    }
    
    /**
     * Start listening for voice commands
     */
    fun startListening() {
        val ctx = context ?: return
        val recognizer = speechRecognizer ?: return
        
        _voiceState.value = VoiceState.Listening
        _recognizedText.value = ""
        
        val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, java.util.Locale.US)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: android.os.Bundle?) {
                Log.d(TAG, "Ready for speech")
            }
            
            override fun onBeginningOfSpeech() {
                Log.d(TAG, "Beginning of speech")
            }
            
            override fun onRmsChanged(rmsdB: Float) {
                // Send volume data to VoiceStateManager for orb visualization
                VoiceStateManager.updateVolumeLevel(rmsdB)
            }
            
            override fun onBufferReceived(buffer: ByteArray?) {
                // Audio buffer received
            }
            
            override fun onEndOfSpeech() {
                Log.d(TAG, "End of speech")
                _voiceState.value = VoiceState.Processing
            }
            
            override fun onError(error: Int) {
                Log.e(TAG, "Speech recognition error: $error")
                _voiceState.value = VoiceState.Error
            }
            
            override fun onResults(results: android.os.Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    val text = matches[0]
                    _recognizedText.value = text
                    processVoiceCommand(text)
                }
            }
            
            override fun onPartialResults(partialResults: android.os.Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    _recognizedText.value = matches[0]
                }
            }
            
            override fun onEvent(eventType: Int, params: android.os.Bundle?) {
                // Additional events
            }
        })
        
        recognizer.startListening(intent)
    }
    
    /**
     * Stop listening
     */
    fun stopListening() {
        speechRecognizer?.stopListening()
        _voiceState.value = VoiceState.Idle
    }
    
    /**
     * Process recognized voice command
     */
    private fun processVoiceCommand(text: String) {
        _voiceState.value = VoiceState.Processing
        
        val command = parseVoiceCommand(text)
        _currentCommand.value = command
        
        command.parsedCommand?.let { cmd ->
            executeVoiceCommand(cmd, command.parameters)
        } ?: run {
            // Send to AI for processing if no direct command matched
            sendToAI(text)
        }
    }
    
    /**
     * Parse voice command into structured format
     */
    fun parseVoiceCommand(text: String): VoiceCommand {
        val lowerText = text.lowercase()
        
        // Try to match command patterns
        for ((command, keywords) in commandPatterns) {
            for (keyword in keywords) {
                if (lowerText.contains(keyword)) {
                    val parameters = extractParameters(text, keyword)
                    return VoiceCommand(
                        originalText = text,
                        parsedCommand = command,
                        parameters = parameters,
                        confidence = 0.9f
                    )
                }
            }
        }
        
        // No direct command matched
        return VoiceCommand(
            originalText = text,
            parsedCommand = null,
            parameters = emptyMap(),
            confidence = 0.0f
        )
    }
    
    /**
     * Extract parameters from voice command
     */
    private fun extractParameters(text: String, keyword: String): Map<String, String> {
        val parameters = mutableMapOf<String, String>()
        val lowerText = text.lowercase()
        
        // Extract app name for open commands
        if (keyword in listOf("open", "launch", "start", "run")) {
            val parts = lowerText.split(keyword)
            if (parts.size > 1) {
                val appName = parts[1].trim().removeSuffix(".").removeSuffix("!")
                parameters["app"] = appName
            }
        }
        
        // Extract volume level
        if (keyword in listOf("volume", "sound", "audio")) {
            val numberPattern = "\\d+".toRegex()
            val number = numberPattern.find(lowerText)?.value
            if (number != null) {
                parameters["level"] = number
            }
        }
        
        // Extract brightness level
        if (keyword in listOf("brightness", "screen", "display")) {
            val numberPattern = "\\d+".toRegex()
            val number = numberPattern.find(lowerText)?.value
            if (number != null) {
                parameters["level"] = number
            }
        }
        
        return parameters
    }
    
    /**
     * Execute parsed voice command
     */
    private fun executeVoiceCommand(command: String, parameters: Map<String, String>) {
        _voiceState.value = VoiceState.Executing
        
        when (command) {
            "open" -> {
                val appName = parameters["app"] ?: ""
                CommandExecutionManager.launchApplication(appName) { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            "volume" -> {
                val level = parameters["level"]?.toIntOrNull() ?: 50
                CommandExecutionManager.setVolume(level) { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            "brightness" -> {
                val level = parameters["level"]?.toIntOrNull() ?: 100
                CommandExecutionManager.setBrightness(level) { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            "media" -> {
                val action = parameters["action"] ?: "play"
                CommandExecutionManager.mediaAction(action) { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            "lock" -> {
                CommandExecutionManager.lockDesktop { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            "system" -> {
                CommandExecutionManager.getSystemStatus { success, result ->
                    _voiceState.value = if (success) VoiceState.Idle else VoiceState.Error
                }
            }
            else -> {
                // Send to AI for processing
                sendToAI(parameters.toString())
            }
        }
    }
    
    /**
     * Send command to AI for processing
     */
    private fun sendToAI(text: String) {
        // This would send the text to the AI system for natural language processing
        // For now, we'll just log it
        Log.d(TAG, "Sending to AI: $text")
        _voiceState.value = VoiceState.Idle
    }
    
    /**
     * Cleanup
     */
    fun cleanup() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }
}