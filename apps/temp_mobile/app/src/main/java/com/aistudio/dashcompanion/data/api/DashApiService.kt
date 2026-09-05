package com.aistudio.dashcompanion.data.api

import com.aistudio.dashcompanion.data.config.AppConfig
import com.aistudio.dashcompanion.data.model.*
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import java.util.concurrent.TimeUnit

object DashApiService {

    private val moshi = com.squareup.moshi.Moshi.Builder()
        .add(com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory())
        .build()

    // BODY-level logging dumps Authorization headers and response bodies to
    // logcat — allowed in debug builds ONLY. Release builds log nothing.
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (com.aistudio.dashcompanion.BuildConfig.DEBUG) {
            HttpLoggingInterceptor.Level.BODY
        } else {
            HttpLoggingInterceptor.Level.NONE
        }
        redactHeader("Authorization")
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor { chain ->
            val originalRequest = chain.request()
            val requestBuilder = originalRequest.newBuilder()
            
            // Always use the latest token from AppConfig
            val token = AppConfig.accessToken
            if (!token.isNullOrEmpty() && token != "placeholder_token") {
                requestBuilder.header("Authorization", "Bearer $token")
            }
            
            chain.proceed(requestBuilder.build())
        }
        .addInterceptor(loggingInterceptor)
        .connectTimeout(AppConfig.CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(AppConfig.READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(AppConfig.WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        // Enable connection pooling for better performance
        .retryOnConnectionFailure(true)
        .build()

    private var _retrofit: Retrofit? = null
    private var _currentBaseUrl: String? = null

    private fun getRetrofit(): Retrofit {
        val baseUrl = AppConfig.REST_BASE_URL
        if (_retrofit == null || _currentBaseUrl != baseUrl) {
            _currentBaseUrl = baseUrl
            _retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(okHttpClient)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
        }
        return _retrofit!!
    }

    private fun getApi(): DashApi {
        return getRetrofit().create(DashApi::class.java)
    }

    suspend fun login(email: String, password: String): AuthResponse {
        return getApi().login(LoginRequest(email = email, password = password))
    }

    suspend fun getHealth(): StatusResponse {
        return getApi().getHealth()
    }

    suspend fun getConversations(): List<Conversation> {
        return getApi().getConversations()
    }

    suspend fun browseFiles(path: String, showHidden: Boolean = false): BrowseResponse {
        return getApi().browseFiles(path, showHidden)
    }

    suspend fun searchFiles(pattern: String, path: String, maxResults: Int = 50): FileSearchResponse {
        return getApi().searchFiles(pattern, path, maxResults)
    }

    suspend fun previewFile(path: String, maxLines: Int = 50): FilePreviewResponse {
        return getApi().previewFile(path, maxLines)
    }

    suspend fun copyFile(source: String, destination: String): FileOperationResponse {
        return getApi().copyFile(FileCopyMoveRequest(source, destination))
    }

    suspend fun moveFile(source: String, destination: String): FileOperationResponse {
        return getApi().moveFile(FileCopyMoveRequest(source, destination))
    }

    suspend fun renameFile(path: String, newName: String): FileOperationResponse {
        return getApi().renameFile(FileRenameRequest(path, newName))
    }

    suspend fun deleteFile(path: String, permanent: Boolean = false): FileOperationResponse {
        return getApi().deleteFile(FileDeleteRequest(path, permanent))
    }

    suspend fun getVolume(): VolumeResponse {
        return getApi().getVolume()
    }

    suspend fun setVolume(level: Int): VolumeResponse {
        return getApi().setVolume(VolumeSetRequest(level))
    }

    suspend fun setMute(muted: Boolean = true): VolumeResponse {
        return getApi().setMute(MuteRequest(muted))
    }

    suspend fun getBrightness(): BrightnessResponse {
        return getApi().getBrightness()
    }

    suspend fun setBrightness(level: Int): BrightnessResponse {
        return getApi().setBrightness(BrightnessSetRequest(level))
    }

    suspend fun getClipboard(): ClipboardResponse {
        return getApi().getClipboard()
    }

    suspend fun setClipboard(text: String): ClipboardResponse {
        return getApi().setClipboard(ClipboardWriteRequest(text))
    }

    suspend fun clipboardClear(): PowerResponse {
        return getApi().clipboardClear()
    }

    suspend fun mouseMove(x: Int, y: Int): StatusResponse {
        return getApi().mouseMove(MouseMoveRequest(x, y))
    }

    suspend fun mouseClick(button: String = "left", x: Int? = null, y: Int? = null): StatusResponse {
        return getApi().mouseClick(MouseClickRequest(button, x, y))
    }

    suspend fun mouseDoubleClick(): StatusResponse {
        return getApi().mouseDoubleClick()
    }

    suspend fun mouseScroll(clicks: Int = 1): StatusResponse {
        return getApi().mouseScroll(clicks)
    }

    suspend fun mousePosition(): StatusResponse {
        return getApi().mousePosition()
    }

    suspend fun keyboardType(text: String): StatusResponse {
        return getApi().keyboardType(KeyTextRequest(text))
    }

    suspend fun keyboardPress(key: String): StatusResponse {
        return getApi().keyboardPress(KeyPressRequest(key))
    }

    suspend fun keyboardHotkey(keys: List<String>): StatusResponse {
        return getApi().keyboardHotkey(KeyboardHotkeyRequest(keys))
    }

    suspend fun takeScreenshot(): StatusResponse {
        return getApi().takeScreenshot()
    }

    suspend fun getScreenshot(): ScreenshotResponse {
        return getApi().getScreenshot()
    }

    suspend fun shutdown(force: Boolean = false): PowerResponse {
        return getApi().shutdown(PowerRequest(force))
    }

    suspend fun restart(force: Boolean = false): PowerResponse {
        return getApi().restart(PowerRequest(force))
    }

    suspend fun lock(): PowerResponse {
        return getApi().lock()
    }

    suspend fun sleep(): PowerResponse {
        return getApi().sleep()
    }

    suspend fun hibernate(): PowerResponse {
        return getApi().hibernate()
    }

    suspend fun logoff(force: Boolean = false): PowerResponse {
        return getApi().logoff(force)
    }

    suspend fun listWindows(): StatusResponse {
        return getApi().listWindows()
    }

    suspend fun focusWindow(title: String): StatusResponse {
        return getApi().focusWindow(WindowActionRequest(title))
    }

    suspend fun closeWindow(title: String): StatusResponse {
        return getApi().closeWindow(WindowActionRequest(title))
    }

    suspend fun minimizeWindow(title: String): StatusResponse {
        return getApi().minimizeWindow(WindowActionRequest(title))
    }

    suspend fun maximizeWindow(title: String): StatusResponse {
        return getApi().maximizeWindow(WindowActionRequest(title))
    }

    suspend fun getActiveWindow(): StatusResponse {
        return getApi().getActiveWindow()
    }

    suspend fun showDesktopNotification(title: String, message: String, duration: Int = 5): PowerResponse {
        return getApi().showNotification(NotificationRequest(title, message, duration))
    }

    // --- AUTOMATION ---
    suspend fun getAutomationRules(): AutomationRulesResponse {
        return getApi().getAutomationRules()
    }

    suspend fun createAutomationRule(request: AutomationRuleRequest): AutomationRuleResponse {
        return getApi().createAutomationRule(request)
    }

    suspend fun updateAutomationRule(id: String, request: AutomationRuleUpdateRequest): AutomationRuleResponse {
        return getApi().updateAutomationRule(id, request)
    }

    suspend fun deleteAutomationRule(id: String): PowerResponse {
        return getApi().deleteAutomationRule(id)
    }

    suspend fun enableAutomationRule(id: String): PowerResponse {
        return getApi().enableAutomationRule(id)
    }

    suspend fun disableAutomationRule(id: String): PowerResponse {
        return getApi().disableAutomationRule(id)
    }

    // --- NOTIFICATIONS ---
    suspend fun getNotifications(): NotificationsResponse {
        return getApi().getNotifications()
    }

    suspend fun markNotificationsRead(request: NotificationsReadRequest): PowerResponse {
        return getApi().markNotificationsRead(request)
    }

    suspend fun clearNotifications(): PowerResponse {
        return getApi().clearNotifications()
    }

    // --- MEMORIES ---
    suspend fun getMemories(search: String? = null, type: String? = null): MemoriesResponse {
        return getApi().getMemories(search, type)
    }

    suspend fun createMemory(request: CreateMemoryRequest): MemoryResponse {
        return getApi().createMemory(request)
    }

    suspend fun deleteMemory(id: String): PowerResponse {
        return getApi().deleteMemory(id)
    }

    suspend fun pinMemory(id: String): PowerResponse {
        return getApi().pinMemory(id)
    }

    suspend fun unpinMemory(id: String): PowerResponse {
        return getApi().unpinMemory(id)
    }

    // --- PROJECTS ---
    suspend fun getProjects(search: String? = null): ProjectsResponse {
        return getApi().getProjects(search)
    }

    suspend fun createProject(request: CreateProjectRequest): ProjectResponse {
        return getApi().createProject(request)
    }

    suspend fun updateProject(id: String, request: UpdateProjectRequest): ProjectResponse {
        return getApi().updateProject(id, request)
    }

    suspend fun deleteProject(id: String): PowerResponse {
        return getApi().deleteProject(id)
    }

    suspend fun syncProject(id: String): PowerResponse {
        return getApi().syncProject(id)
    }

    // --- MEDIA ---
    suspend fun getMediaStatus(): MediaStatusResponse {
        return getApi().getMediaStatus()
    }

    suspend fun mediaPlay(): PowerResponse {
        return getApi().mediaPlay()
    }

    suspend fun mediaPause(): PowerResponse {
        return getApi().mediaPause()
    }

    suspend fun mediaNext(): PowerResponse {
        return getApi().mediaNext()
    }

    suspend fun mediaPrevious(): PowerResponse {
        return getApi().mediaPrevious()
    }

    suspend fun mediaStop(): PowerResponse {
        return getApi().mediaStop()
    }

    // --- DASHBOARD STATS ---
    suspend fun getDashboardStats(): DashboardStatsResponse {
        return getApi().getDashboardStats()
    }

    // --- IMAGE UPLOAD & ANALYSIS ---
    suspend fun uploadImage(body: okhttp3.RequestBody, analyze: Boolean = true, ocr: Boolean = true): ImageUploadResponse {
        // We use the raw request body here as DashRepository builds a MultipartBody
        return getApi().uploadImageRaw(body, analyze, ocr)
    }

    suspend fun analyzeImage(imageBase64: String): ImageAnalysisResult {
        return getApi().analyzeImage(imageBase64)
    }

    // --- FILE TRANSFER ---
    suspend fun uploadFileToPc(request: FileUploadRequest): FileTransferResult {
        return getApi().uploadFileToPc(request)
    }

    suspend fun downloadFile(request: FileDownloadRequest): FileTransferResult {
        return getApi().downloadFile(request)
    }

    suspend fun getTransferDestinations(): Map<String, String> {
        return getApi().getTransferDestinations()
    }
}

interface DashApi {
    @GET("health")
    suspend fun getHealth(): StatusResponse

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse

    @GET("conversations")
    suspend fun getConversations(): List<Conversation>

    @GET("files/browse")
    suspend fun browseFiles(
        @Query("path") path: String,
        @Query("show_hidden") showHidden: Boolean = false
    ): BrowseResponse

    @GET("files/search")
    suspend fun searchFiles(
        @Query("pattern") pattern: String,
        @Query("path") path: String,
        @Query("max_results") maxResults: Int = 50
    ): FileSearchResponse

    @GET("files/preview")
    suspend fun previewFile(
        @Query("path") path: String,
        @Query("max_lines") maxLines: Int = 50
    ): FilePreviewResponse

    @POST("files/copy")
    suspend fun copyFile(@Body request: FileCopyMoveRequest): FileOperationResponse

    @POST("files/move")
    suspend fun moveFile(@Body request: FileCopyMoveRequest): FileOperationResponse

    @POST("files/rename")
    suspend fun renameFile(@Body request: FileRenameRequest): FileOperationResponse

    @POST("files/delete")
    suspend fun deleteFile(@Body request: FileDeleteRequest): FileOperationResponse

    @GET("desktop/volume")
    suspend fun getVolume(): VolumeResponse

    @POST("desktop/volume")
    suspend fun setVolume(@Body request: VolumeSetRequest): VolumeResponse

    @POST("desktop/volume/mute")
    suspend fun setMute(@Body request: MuteRequest): VolumeResponse

    @GET("desktop/brightness")
    suspend fun getBrightness(): BrightnessResponse

    @POST("desktop/brightness")
    suspend fun setBrightness(@Body request: BrightnessSetRequest): BrightnessResponse

    @GET("desktop/clipboard")
    suspend fun getClipboard(): ClipboardResponse

    @POST("desktop/clipboard")
    suspend fun setClipboard(@Body request: ClipboardWriteRequest): ClipboardResponse

    @DELETE("desktop/clipboard")
    suspend fun clipboardClear(): PowerResponse

    @POST("desktop/mouse/move")
    suspend fun mouseMove(@Body request: MouseMoveRequest): StatusResponse

    @POST("desktop/mouse/click")
    suspend fun mouseClick(@Body request: MouseClickRequest): StatusResponse

    @POST("desktop/mouse/double-click")
    suspend fun mouseDoubleClick(): StatusResponse

    @POST("desktop/mouse/scroll")
    suspend fun mouseScroll(@Query("clicks") clicks: Int = 1): StatusResponse

    @GET("desktop/mouse/position")
    suspend fun mousePosition(): StatusResponse

    @POST("desktop/keyboard/type")
    suspend fun keyboardType(@Body request: KeyTextRequest): StatusResponse

    @POST("desktop/keyboard/press")
    suspend fun keyboardPress(@Body request: KeyPressRequest): StatusResponse

    @POST("desktop/keyboard/hotkey")
    suspend fun keyboardHotkey(@Body request: KeyboardHotkeyRequest): StatusResponse

    @POST("desktop/screenshot")
    suspend fun takeScreenshot(): StatusResponse

    @GET("desktop/screenshot")
    suspend fun getScreenshot(): ScreenshotResponse

    @POST("desktop/power/shutdown")
    suspend fun shutdown(@Body request: PowerRequest): PowerResponse

    @POST("desktop/power/restart")
    suspend fun restart(@Body request: PowerRequest): PowerResponse

    @POST("desktop/power/lock")
    suspend fun lock(): PowerResponse

    @POST("desktop/power/sleep")
    suspend fun sleep(): PowerResponse

    @POST("desktop/power/hibernate")
    suspend fun hibernate(): PowerResponse

    @POST("desktop/power/logoff")
    suspend fun logoff(@Query("force") force: Boolean = false): PowerResponse

    @POST("desktop/notification")
    suspend fun showNotification(@Body request: NotificationRequest): PowerResponse

    @GET("windows")
    suspend fun listWindows(): StatusResponse

    @POST("windows/focus")
    suspend fun focusWindow(@Body request: WindowActionRequest): StatusResponse

    @POST("windows/close")
    suspend fun closeWindow(@Body request: WindowActionRequest): StatusResponse

    @POST("windows/minimize")
    suspend fun minimizeWindow(@Body request: WindowActionRequest): StatusResponse

    @POST("windows/maximize")
    suspend fun maximizeWindow(@Body request: WindowActionRequest): StatusResponse

    @GET("windows/active")
    suspend fun getActiveWindow(): StatusResponse

    // --- AUTOMATION ---
    @GET("automation/rules")
    suspend fun getAutomationRules(): AutomationRulesResponse

    @POST("automation/rules")
    suspend fun createAutomationRule(@Body request: AutomationRuleRequest): AutomationRuleResponse

    @PUT("automation/rules/{id}")
    suspend fun updateAutomationRule(@Path("id") id: String, @Body request: AutomationRuleUpdateRequest): AutomationRuleResponse

    @DELETE("automation/rules/{id}")
    suspend fun deleteAutomationRule(@Path("id") id: String): PowerResponse

    @POST("automation/rules/{id}/enable")
    suspend fun enableAutomationRule(@Path("id") id: String): PowerResponse

    @POST("automation/rules/{id}/disable")
    suspend fun disableAutomationRule(@Path("id") id: String): PowerResponse

    // --- NOTIFICATIONS ---
    @GET("notifications")
    suspend fun getNotifications(): NotificationsResponse

    @POST("notifications/read")
    suspend fun markNotificationsRead(@Body request: NotificationsReadRequest): PowerResponse

    @DELETE("notifications")
    suspend fun clearNotifications(): PowerResponse

    // --- MEMORIES ---
    @GET("memories")
    suspend fun getMemories(@Query("search") search: String? = null, @Query("type") type: String? = null): MemoriesResponse

    @POST("memories")
    suspend fun createMemory(@Body request: CreateMemoryRequest): MemoryResponse

    @DELETE("memories/{id}")
    suspend fun deleteMemory(@Path("id") id: String): PowerResponse

    @POST("memories/{id}/pin")
    suspend fun pinMemory(@Path("id") id: String): PowerResponse

    @POST("memories/{id}/unpin")
    suspend fun unpinMemory(@Path("id") id: String): PowerResponse

    // --- PROJECTS ---
    @GET("projects")
    suspend fun getProjects(@Query("search") search: String? = null): ProjectsResponse

    @POST("projects")
    suspend fun createProject(@Body request: CreateProjectRequest): ProjectResponse

    @PUT("projects/{id}")
    suspend fun updateProject(@Path("id") id: String, @Body request: UpdateProjectRequest): ProjectResponse

    @DELETE("projects/{id}")
    suspend fun deleteProject(@Path("id") id: String): PowerResponse

    @POST("projects/{id}/sync")
    suspend fun syncProject(@Path("id") id: String): PowerResponse

    // --- MEDIA ---
    @GET("media/status")
    suspend fun getMediaStatus(): MediaStatusResponse

    @POST("media/play")
    suspend fun mediaPlay(): PowerResponse

    @POST("media/pause")
    suspend fun mediaPause(): PowerResponse

    @POST("media/next")
    suspend fun mediaNext(): PowerResponse

    @POST("media/previous")
    suspend fun mediaPrevious(): PowerResponse

    @POST("media/stop")
    suspend fun mediaStop(): PowerResponse

    // --- FILES UPLOAD/DOWNLOAD ---
    @Multipart
    @POST("files/upload")
    suspend fun uploadFile(
        @Part file: okhttp3.MultipartBody.Part,
        @Query("path") path: String
    ): FileOperationResponse

    @GET("files/download")
    suspend fun downloadFile(@Query("path") path: String): okhttp3.ResponseBody

    // --- DASHBOARD STATS ---
    @GET("dashboard/stats")
    suspend fun getDashboardStats(): DashboardStatsResponse

    // --- IMAGE UPLOAD & ANALYSIS ---
    @Multipart
    @POST("images/upload")
    suspend fun uploadImage(
        @Part file: okhttp3.MultipartBody.Part,
        @Query("analyze") analyze: Boolean = true,
        @Query("ocr") ocr: Boolean = true
    ): ImageUploadResponse

    @POST("images/upload")
    suspend fun uploadImageRaw(
        @Body body: okhttp3.RequestBody,
        @Query("analyze") analyze: Boolean = true,
        @Query("ocr") ocr: Boolean = true
    ): ImageUploadResponse

    @POST("images/analyze")
    suspend fun analyzeImage(@Body imageBase64: String): ImageAnalysisResult

    // --- FILE TRANSFER ---
    @POST("transfer/upload")
    suspend fun uploadFileToPc(@Body request: FileUploadRequest): FileTransferResult

    @POST("transfer/download")
    suspend fun downloadFile(@Body request: FileDownloadRequest): FileTransferResult

    @GET("transfer/destinations")
    suspend fun getTransferDestinations(): Map<String, String>
}

// Request/Response Models
data class LoginRequest(val email: String, val password: String)
data class AuthResponse(val access_token: String, val refresh_token: String, val token_type: String = "bearer")

data class FileCopyMoveRequest(val source: String, val destination: String)
data class FileRenameRequest(val path: String, val new_name: String)
data class FileDeleteRequest(val path: String, val permanent: Boolean = false)
data class FileSearchResponse(val pattern: String = "", val path: String = "", val results: List<FileInfo> = emptyList(), val count: Int = 0)

data class VolumeSetRequest(val level: Int)
data class MuteRequest(val muted: Boolean = true)
data class VolumeResponse(val volume: Float = 0f, val muted: Boolean = false, val summary: String = "")

data class BrightnessSetRequest(val level: Int)
data class BrightnessResponse(val brightness: Int = 0, val summary: String = "")

data class ClipboardWriteRequest(val text: String)
data class ClipboardResponse(val text: String = "", val summary: String = "")

data class MouseMoveRequest(val x: Int, val y: Int)
data class MouseClickRequest(val button: String, val x: Int? = null, val y: Int? = null)

data class KeyTextRequest(val text: String)
data class KeyPressRequest(val key: String)
data class KeyboardHotkeyRequest(val keys: List<String>)

data class PowerRequest(val force: Boolean = false, val timeout: Int = 30)
data class PowerResponse(val summary: String)
data class StatusResponse(val status: String, val details: Map<String, Any> = emptyMap())

data class WindowActionRequest(val title: String)
data class FilePreviewResponse(val name: String, val path: String, val size_bytes: Long, val content: String, val type: String, val total_lines: Int? = null, val truncated: Boolean = false, val image_width: Int? = null, val image_height: Int? = null)

data class NotificationRequest(val title: String = "DASH", val message: String = "", val duration: Int = 5)

// --- AUTOMATION MODELS ---
data class AutomationRule(
    val id: String = "",
    val name: String = "",
    val description: String = "",
    val enabled: Boolean = false,
    val trigger: String = "",
    val action: String = "",
    val created_at: String = "",
    val updated_at: String = ""
)

data class AutomationRulesResponse(
    val rules: List<AutomationRule> = emptyList(),
    val count: Int = 0
)

data class AutomationRuleRequest(
    val name: String,
    val description: String = "",
    val trigger: String,
    val action: String,
    val enabled: Boolean = true
)

data class AutomationRuleUpdateRequest(
    val name: String? = null,
    val description: String? = null,
    val trigger: String? = null,
    val action: String? = null,
    val enabled: Boolean? = null
)

data class AutomationRuleResponse(
    val rule: AutomationRule? = null,
    val status: String = "ok",
    val summary: String = ""
)

// --- NOTIFICATION MODELS ---
data class NotificationItem(
    val id: String = "",
    val title: String = "",
    val text: String = "",
    val source: String = "",
    val timestamp: Long = 0,
    val read: Boolean = false,
    val type: String = "info"
)

data class NotificationsResponse(
    val notifications: List<NotificationItem> = emptyList(),
    val count: Int = 0,
    val unread_count: Int = 0
)

data class NotificationsReadRequest(
    val ids: List<String>? = null,
    val all: Boolean = false
)

// --- MEMORY MODELS ---
data class Memory(
    val id: String = "",
    val content: String = "",
    val type: String = "conversation",
    val pinned: Boolean = false,
    val created_at: String = "",
    val updated_at: String = "",
    val tags: List<String> = emptyList()
)

data class MemoriesResponse(
    val memories: List<Memory> = emptyList(),
    val count: Int = 0
)

data class CreateMemoryRequest(
    val content: String,
    val type: String = "custom",
    val tags: List<String> = emptyList()
)

data class MemoryResponse(
    val memory: Memory? = null,
    val status: String = "ok",
    val summary: String = ""
)

// --- PROJECT MODELS ---
data class Project(
    val id: String = "",
    val name: String = "",
    val description: String = "",
    val path: String = "",
    val language: String = "",
    val last_opened: String = "",
    val created_at: String = "",
    val updated_at: String = ""
)

data class ProjectsResponse(
    val projects: List<Project> = emptyList(),
    val count: Int = 0
)

data class CreateProjectRequest(
    val name: String,
    val description: String = "",
    val path: String = "",
    val language: String = ""
)

data class UpdateProjectRequest(
    val name: String? = null,
    val description: String? = null,
    val path: String? = null,
    val language: String? = null
)

data class ProjectResponse(
    val project: Project? = null,
    val status: String = "ok",
    val summary: String = ""
)

// --- MEDIA MODELS ---
data class MediaStatus(
    val is_playing: Boolean = false,
    val title: String = "",
    val artist: String = "",
    val album: String = "",
    val duration: Long = 0,
    val position: Long = 0,
    val volume: Float = 0f,
    val muted: Boolean = false,
    val source: String = ""
)

data class MediaStatusResponse(
    val status: String = "ok",
    val media: MediaStatus = MediaStatus()
)

// --- SCREENSHOT ---
data class ScreenshotResponse(
    val status: String = "ok",
    val image_base64: String = "",
    val width: Int = 0,
    val height: Int = 0,
    val format: String = "png",
    val timestamp: Long = 0
)

// --- DASHBOARD STATS ---
data class DashboardStats(
    val desktop_online: Boolean = false,
    val cpu_percent: Double = 0.0,
    val ram_percent: Double = 0.0,
    val gpu_percent: Double = 0.0,
    val active_model: String = "",
    val voice_status: String = "idle",
    val websocket_status: String = "disconnected",
    val memory_count: Int = 0,
    val project_count: Int = 0,
    val automation_count: Int = 0
)

data class DashboardStatsResponse(
    val status: String = "ok",
    val stats: DashboardStats = DashboardStats()
)

// --- IMAGE UPLOAD & ANALYSIS ---
data class ImageAnalysisResult(
    val status: String = "ok",
    val ocr_text: String = "",
    val ocr_confidence: Float = 0f,
    val summary: String = "",
    val details: Map<String, Any> = emptyMap()
)

data class ImageUploadResponse(
    val status: String = "ok",
    val image_id: String = "",
    val filename: String = "",
    val size_bytes: Long = 0,
    val analysis: ImageAnalysisResult? = null
)

// --- FILE TRANSFER ---
data class FileTransferResult(
    val status: String = "ok",
    val message: String = "",
    val file_id: String = "",
    val filename: String = "",
    val size_bytes: Long = 0,
    val path: String = "",
    val details: Map<String, Any> = emptyMap()
)

data class FileUploadRequest(
    val filename: String,
    val data_base64: String,
    val destination: String = "downloads"
)

data class FileDownloadRequest(
    val path: String
)
