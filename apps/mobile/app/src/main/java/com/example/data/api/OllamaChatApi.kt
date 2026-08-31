package com.example.data.api

import android.util.Log
import com.example.data.config.AppConfig
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSource
import java.util.concurrent.TimeUnit

/**
 * OllamaChatApi — talks to the backend's Ollama proxy endpoints.
 *
 * Flow: Android → backend proxy → Ollama (when PC is on)
 *       Android → EC2 → (503 + tunnel URL when PC is off)
 *
 * Uses OkHttp directly for simplicity, Moshi for JSON.
 */
object OllamaChatApi {
    private const val TAG = "OllamaChatApi"
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS) // Ollama can be slow
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json".toMediaType()

    private fun buildUrl(path: String): String {
        val base = AppConfig.REST_BASE_URL.trimEnd('/')
        return "$base$path"
    }

    private fun buildCloudUrl(path: String): String {
        val base = AppConfig.CLOUD_BASE_URL.trimEnd('/')
        return "$base/api/v1$path"
    }

    /**
     * Check if Ollama is running (local or tunnel).
     */
    suspend fun getStatus(): OllamaStatusResponse {
        // Try local first
        try {
            val request = Request.Builder()
                .url(buildUrl("ollama/status"))
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val adapter = moshi.adapter(OllamaStatusResponse::class.java)
                return adapter.fromJson(body) ?: OllamaStatusResponse()
            }
        } catch (e: Exception) {
            Log.d(TAG, "Local status check failed: ${e.message}")
        }

        // Try cloud
        try {
            val request = Request.Builder()
                .url(buildCloudUrl("ollama/status"))
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val adapter = moshi.adapter(OllamaStatusResponse::class.java)
                return adapter.fromJson(body) ?: OllamaStatusResponse()
            }
        } catch (e: Exception) {
            Log.d(TAG, "Cloud status check failed: ${e.message}")
        }

        return OllamaStatusResponse()
    }

    /**
     * List available Ollama models.
     */
    suspend fun getModels(): OllamaModelsResponse {
        // Try local first
        try {
            val request = Request.Builder()
                .url(buildUrl("ollama/models"))
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val adapter = moshi.adapter(OllamaModelsResponse::class.java)
                return adapter.fromJson(body) ?: OllamaModelsResponse(emptyList())
            }
        } catch (e: Exception) {
            Log.d(TAG, "Local models failed: ${e.message}")
        }

        // Try cloud
        try {
            val request = Request.Builder()
                .url(buildCloudUrl("ollama/models"))
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val adapter = moshi.adapter(OllamaModelsResponse::class.java)
                return adapter.fromJson(body) ?: OllamaModelsResponse(emptyList())
            }
        } catch (e: Exception) {
            Log.d(TAG, "Cloud models failed: ${e.message}")
        }

        return OllamaModelsResponse(emptyList())
    }

    /**
     * Send a chat message to Ollama (non-streaming).
     */
    suspend fun chat(model: String, messages: List<OllamaMessage>): OllamaChatResponse? {
        val requestAdapter = moshi.adapter(OllamaChatRequest::class.java)
        val json = requestAdapter.toJson(
            OllamaChatRequest(model = model, messages = messages, stream = false)
        )

        // Try local first
        try {
            val request = Request.Builder()
                .url(buildUrl("ollama/chat"))
                .post(json.toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: return null
                val adapter = moshi.adapter(OllamaChatResponse::class.java)
                return adapter.fromJson(body)
            }
        } catch (e: Exception) {
            Log.d(TAG, "Local chat failed: ${e.message}")
        }

        // Try cloud
        try {
            val request = Request.Builder()
                .url(buildCloudUrl("ollama/chat"))
                .post(json.toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: return null
                val adapter = moshi.adapter(OllamaChatResponse::class.java)
                return adapter.fromJson(body)
            }
        } catch (e: Exception) {
            Log.d(TAG, "Cloud chat failed: ${e.message}")
        }

        return null
    }

    /**
     * Send a chat message with streaming (callback-based).
     * Calls onToken for each token, onComplete when done.
     */
    suspend fun chatStream(
        model: String,
        messages: List<OllamaMessage>,
        onToken: (String) -> Unit,
        onComplete: (String) -> Unit
    ) {
        val requestAdapter = moshi.adapter(OllamaChatRequest::class.java)
        val json = requestAdapter.toJson(
            OllamaChatRequest(model = model, messages = messages, stream = true)
        )

        val urls = listOf(buildUrl("ollama/chat"), buildCloudUrl("ollama/chat"))
        val chunkAdapter = moshi.adapter(OllamaStreamChunk::class.java)

        for (url in urls) {
            try {
                val request = Request.Builder()
                    .url(url)
                    .post(json.toRequestBody(jsonMediaType))
                    .build()
                val response = client.newCall(request).execute()

                if (!response.isSuccessful) continue

                val source: BufferedSource? = response.body?.source()
                if (source == null) continue

                val fullResponse = StringBuilder()

                source.use { s ->
                    while (!s.exhausted()) {
                        val line = s.readUtf8Line() ?: continue
                        if (line.isBlank()) continue
                        try {
                            val chunk = chunkAdapter.fromJson(line)
                            val content = chunk?.message?.content ?: ""
                            if (content.isNotEmpty()) {
                                fullResponse.append(content)
                                onToken(content)
                            }
                        } catch (_: Exception) {
                            // Skip malformed lines
                        }
                    }
                }
                onComplete(fullResponse.toString())
                return
            } catch (e: Exception) {
                Log.d(TAG, "Stream from $url failed: ${e.message}")
            }
        }

        onComplete("")
    }
}

// ── Data Models ─────────────────────────────────────────────

data class OllamaStatusResponse(
    val local_running: Boolean = false,
    val tunnel_url: String = "",
    val tunnel_available: Boolean = false,
    val ollama_url: String = ""
)

data class OllamaModelsResponse(
    val models: List<OllamaModel> = emptyList()
)

data class OllamaModel(
    val name: String = "",
    val model: String = "",
    val details: OllamaModelDetails? = null
)

data class OllamaModelDetails(
    val family: String = "",
    val parameter_size: String = "",
    val quantization_level: String = ""
)

data class OllamaMessage(
    val role: String,
    val content: String
)

data class OllamaChatRequest(
    val model: String,
    val messages: List<OllamaMessage>,
    val stream: Boolean = false
)

data class OllamaChatResponse(
    val model: String = "",
    val message: OllamaMessage? = null,
    val done: Boolean = false,
    val done_reason: String = "",
    val total_duration: Long = 0,
    val eval_count: Int = 0
)

data class OllamaStreamChunk(
    val model: String = "",
    val message: OllamaMessage? = null,
    val done: Boolean = false
)
