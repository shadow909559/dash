package com.example.data.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import com.example.data.config.AppConfig
import com.example.data.security.SecurityManager
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.util.concurrent.TimeUnit

/**
 * Unified DASH API client. Singleton object used by DashRepository and screens.
 * All methods map 1:1 to backend /api/v1/ routes.
 */
object DashApiService {
    private var api: DashApi? = null

    /** Reset the cached Retrofit client so next call uses current AppConfig. */
    fun reset() {
        api = null
    }

    private fun getApi(): DashApi {
        if (api == null) {
            val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BODY }
            val client = OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .addInterceptor { chain ->
                    val currentToken = com.example.data.config.AppConfig.accessToken
                    val req = chain.request().newBuilder()
                    if (!currentToken.isNullOrBlank()) req.addHeader("Authorization", "Bearer $currentToken")
                    chain.proceed(req.build())
                }
                .addInterceptor(logging)
                .build()

            val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
            api = Retrofit.Builder()
                .baseUrl(AppConfig.REST_BASE_URL)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(DashApi::class.java)
        }
        return api!!
    }

    // ─── Auth ───
    suspend fun login(email: String, password: String): AuthResponse =
        getApi().login(LoginRequest(email, password))

    // ─── Health / Status ───
    suspend fun getHealth(): StatusResponse = getApi().getHealth()
    suspend fun getStatusOverview(): StatusResponse = getApi().getStatusOverview()

    // ─── Conversations ───
    suspend fun getConversations(): List<Conversation> = getApi().getConversations()

    // ─── Memory ───
    suspend fun getMemories(search: String? = null, type: String? = null): MemoriesResponse =
        getApi().getMemories(search, type)
    suspend fun createMemory(request: CreateMemoryRequest): MemoryResponse = getApi().createMemory(request)
    suspend fun deleteMemory(id: String): PowerResponse = getApi().deleteMemory(id)

    // ─── Projects ───
    suspend fun getProjects(search: String? = null): ProjectsResponse = getApi().getProjects(search)
    suspend fun createProject(request: CreateProjectRequest): ProjectResponse = getApi().createProject(request)

    // ─── Desktop: Volume ───
    suspend fun getVolume(): VolumeResponse = getApi().getVolume()
    suspend fun setVolume(level: Int): VolumeResponse = getApi().setVolume(VolumeSetRequest(level))
    suspend fun toggleMute(muted: Boolean = true): VolumeResponse = getApi().toggleMute(MuteRequest(muted))
    suspend fun volumeUp(): VolumeResponse = getApi().volumeUp()
    suspend fun volumeDown(): VolumeResponse = getApi().volumeDown()

    // ─── Desktop: Brightness ───
    suspend fun getBrightness(): BrightnessResponse = getApi().getBrightness()
    suspend fun setBrightness(level: Int): BrightnessResponse = getApi().setBrightness(BrightnessSetRequest(level))

    // ─── Desktop: Clipboard ───
    suspend fun getClipboard(): ClipboardResponse = getApi().getClipboard()
    suspend fun setClipboard(text: String): ClipboardResponse = getApi().setClipboard(ClipboardWriteRequest(text))
    suspend fun clearClipboard(): PowerResponse = getApi().clearClipboard()

    // ─── Desktop: Mouse ───
    suspend fun mouseMove(x: Int, y: Int): StatusResponse = getApi().mouseMove(MouseMoveRequest(x, y))
    suspend fun mouseClick(button: String = "left"): StatusResponse = getApi().mouseClick(MouseClickRequest(button))
    suspend fun mouseDoubleClick(): StatusResponse = getApi().mouseDoubleClick()
    suspend fun mouseScroll(clicks: Int = 3): StatusResponse = getApi().mouseScroll(clicks)
    suspend fun getMousePosition(): StatusResponse = getApi().getMousePosition()

    // ─── Desktop: Keyboard ───
    suspend fun keyboardType(text: String): StatusResponse = getApi().keyboardType(KeyTextRequest(text))
    suspend fun keyboardPress(key: String): StatusResponse = getApi().keyboardPress(KeyPressRequest(key))
    suspend fun keyboardHotkey(keys: List<String>): StatusResponse = getApi().keyboardHotkey(keys)

    // ─── Desktop: Screenshot ───
    suspend fun takeScreenshot(): StatusResponse = getApi().takeScreenshot()
    suspend fun getScreenshot(): ScreenshotResponse = getApi().getScreenshot()

    // ─── Desktop: Power ───
    suspend fun shutdown(): PowerResponse = getApi().shutdown(PowerRequest())
    suspend fun restart(): PowerResponse = getApi().restart(PowerRequest())
    suspend fun lock(): PowerResponse = getApi().lock()
    suspend fun sleep(): PowerResponse = getApi().sleep(PowerRequest())
    suspend fun hibernate(): PowerResponse = getApi().hibernate(PowerRequest())
    suspend fun logoff(): PowerResponse = getApi().logoff(PowerRequest())
    suspend fun abortShutdown(): PowerResponse = getApi().abortShutdown()

    // ─── Desktop: Approvals ───
    suspend fun getApprovals(): ApprovalResponse = getApi().getApprovals()
    suspend fun approveAction(id: String): StatusResponse = getApi().approveAction(id)
    suspend fun denyAction(id: String): StatusResponse = getApi().denyAction(id)

    // ─── Windows ───
    suspend fun listWindows(): StatusResponse = getApi().listWindows()
    suspend fun focusWindow(title: String): StatusResponse = getApi().focusWindow(mapOf("title" to title))
    suspend fun closeWindow(title: String): StatusResponse = getApi().closeWindow(mapOf("title" to title))
    suspend fun minimizeWindow(title: String): StatusResponse = getApi().minimizeWindow(mapOf("title" to title))
    suspend fun maximizeWindow(title: String): StatusResponse = getApi().maximizeWindow(mapOf("title" to title))

    // ─── Files ───
    suspend fun browseFiles(path: String? = null): FileBrowseResponse = getApi().browseFiles(path)
    suspend fun searchFiles(query: String): FileSearchResponse = getApi().searchFiles(query)
    suspend fun getSpecialFolders(): Map<String, String> = getApi().getSpecialFolders()
    suspend fun getDrives(): FileSearchResponse = getApi().getDrives()

    // ─── Applications ───
    suspend fun searchApplications(query: String): List<AppInfo> = getApi().searchApplications(query)
    suspend fun launchApplication(name: String): StatusResponse = getApi().launchApplication(mapOf("name" to name))
    suspend fun closeApplication(name: String): StatusResponse = getApi().closeApplication(mapOf("name" to name))
    suspend fun listProcesses(): List<Map<String, Any>> = getApi().listProcesses()
    suspend fun renameFile(oldPath: String, newPath: String): PowerResponse = getApi().renameFile(FileRenameRequest(oldPath, newPath))
    suspend fun moveFile(source: String, dest: String): PowerResponse = getApi().moveFile(FileMoveRequest(source, dest))
    suspend fun copyFile(source: String, dest: String): PowerResponse = getApi().copyFile(FileCopyRequest(source, dest))

    // ─── Keyboard ───
    suspend fun typeText(text: String): StatusResponse = getApi().keyboardType(KeyTextRequest(text))
    suspend fun pressKey(key: String): StatusResponse = getApi().keyboardPress(KeyPressRequest(key))
    suspend fun hotkey(keys: List<String>): StatusResponse = getApi().keyboardHotkey(keys)

    // ─── Clipboard ───
    suspend fun readClipboard(): ClipboardResponse = getApi().getClipboard()
    suspend fun writeClipboard(text: String): ClipboardResponse = getApi().setClipboard(ClipboardWriteRequest(text))

    // ─── Files ───
    suspend fun deleteFile(path: String, permanent: Boolean = false): PowerResponse = getApi().deleteFile(FileDeleteRequest(path, permanent))

    // ─── Notifications ───
    suspend fun getNotifications(): NotificationsResponse = getApi().getNotifications()
    suspend fun markNotificationsRead(request: NotificationsReadRequest): PowerResponse = getApi().markNotificationsRead(request)
    suspend fun getNotificationPrefs(): NotificationPrefsResponse = getApi().getNotificationPrefs()
    suspend fun updateNotificationPrefs(request: NotificationPrefsRequest): NotificationPrefsResponse = getApi().updateNotificationPrefs(request)
    suspend fun getWakeWord(): WakeWordResponse = getApi().getWakeWord()
    suspend fun updateWakeWord(request: WakeWordRequest): WakeWordResponse = getApi().updateWakeWord(request)

    // ─── Automation ───
    suspend fun getAutomationRules(): AutomationRulesResponse = getApi().getAutomationRules()

    // ─── Media ───
    suspend fun getMediaStatus(): MediaStatusResponse = getApi().getMediaStatus()
    suspend fun mediaPlay(): PowerResponse = getApi().mediaPlay()
    suspend fun mediaPause(): PowerResponse = getApi().mediaPause()
    suspend fun mediaNext(): PowerResponse = getApi().mediaNext()
    suspend fun mediaPrevious(): PowerResponse = getApi().mediaPrevious()

    // ─── Research (raw JSON — dynamic response shape) ───
    suspend fun rawResearch(query: String, maxResults: Int = 8): Map<String, Any> {
        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
        val url = "${AppConfig.REST_BASE_URL}monitor/research?query=${java.net.URLEncoder.encode(query, "UTF-8")}&max_results=$maxResults"
        val token = AppConfig.accessToken
        val request = okhttp3.Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer ${token ?: ""}")
            .post(okhttp3.RequestBody.create(null, ByteArray(0)))
            .build()
        val resp = client.newCall(request).execute()
        val body = resp.body?.string() ?: throw Exception("Empty response")
        @Suppress("UNCHECKED_CAST")
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        return moshi.adapter(Any::class.java).fromJson(body) as? Map<String, Any>
            ?: throw Exception("Invalid JSON")
    }

    // ─── Device Pairing (unauthenticated endpoint) ───
    suspend fun devicePair(deviceId: String, deviceName: String, pairingCode: String): Map<String, Any> {
        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()
        val moshi2 = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val json = moshi2.adapter(Any::class.java).toJson(mapOf(
            "device_id" to deviceId,
            "device_name" to deviceName,
            "pairing_code" to pairingCode
        ))
        val pairUrl = "${'$'}{AppConfig.REST_BASE_URL}auth/device-pair"
        val reqBody = okhttp3.RequestBody.create(
            "application/json; charset=utf-8".toMediaType(),
            json.toByteArray()
        )
        val request = okhttp3.Request.Builder()
            .url(pairUrl)
            .post(reqBody)
            .build()
        val resp = client.newCall(request).execute()
        val bodyStr = resp.body?.string() ?: throw Exception("Empty response")
        @Suppress("UNCHECKED_CAST")
        return moshi2.adapter(Any::class.java).fromJson(bodyStr) as? Map<String, Any>
            ?: throw Exception("Invalid JSON")
    }

    // --- Remote System Status & Start ---
    suspend fun getRemoteSystemStatus(): RemoteSystemStatusResponse = getApi().getRemoteSystemStatus()

    // --- Remote Start (service management) ---
    suspend fun startService(request: RemoteStartRequest): RemoteStartResponse = getApi().startService(request)

    // --- Wake-on-LAN ---
    suspend fun wakeOnLan(macAddress: String, broadcast: String? = null, count: Int = 3): WolResponse {
        return try {
            getApi().wakeOnLan(WolRequest(mac_address = macAddress, broadcast = broadcast, count = count))
        } catch (e: Exception) {
            WolResponse(summary = "Failed: ${e.message}", mac_address = macAddress, packets_sent = 0)
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Retrofit interface — one-to-one with DASH backend /api/v1/ routes
// ═══════════════════════════════════════════════════════════════════════
interface DashApi {

    // Health
    @GET("health")
    suspend fun getHealth(): StatusResponse
    @GET("status/overview")
    suspend fun getStatusOverview(): StatusResponse

    // Auth
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse

    // Conversations
    @GET("conversations")
    suspend fun getConversations(): List<Conversation>

    // Memory
    @GET("memory")
    suspend fun getMemories(@Query("search") search: String? = null, @Query("type") type: String? = null): MemoriesResponse
    @POST("memory")
    suspend fun createMemory(@Body request: CreateMemoryRequest): MemoryResponse
    @DELETE("memory/{id}")
    suspend fun deleteMemory(@Path("id") id: String): PowerResponse

    // Projects
    @GET("projects")
    suspend fun getProjects(@Query("search") search: String? = null): ProjectsResponse
    @POST("projects")
    suspend fun createProject(@Body request: CreateProjectRequest): ProjectResponse

    // Desktop: Volume
    @GET("desktop/volume")
    suspend fun getVolume(): VolumeResponse
    @POST("desktop/volume")
    suspend fun setVolume(@Body request: VolumeSetRequest): VolumeResponse
    @POST("desktop/volume/mute")
    suspend fun toggleMute(@Body request: MuteRequest): VolumeResponse
    @POST("desktop/volume/up")
    suspend fun volumeUp(): VolumeResponse
    @POST("desktop/volume/down")
    suspend fun volumeDown(): VolumeResponse

    // Desktop: Brightness
    @GET("desktop/brightness")
    suspend fun getBrightness(): BrightnessResponse
    @POST("desktop/brightness")
    suspend fun setBrightness(@Body request: BrightnessSetRequest): BrightnessResponse

    // Desktop: Clipboard
    @GET("desktop/clipboard")
    suspend fun getClipboard(): ClipboardResponse
    @POST("desktop/clipboard")
    suspend fun setClipboard(@Body request: ClipboardWriteRequest): ClipboardResponse
    @DELETE("desktop/clipboard")
    suspend fun clearClipboard(): PowerResponse

    // Desktop: Mouse
    @POST("desktop/mouse/move")
    suspend fun mouseMove(@Body request: MouseMoveRequest): StatusResponse
    @POST("desktop/mouse/click")
    suspend fun mouseClick(@Body request: MouseClickRequest): StatusResponse
    @POST("desktop/mouse/double-click")
    suspend fun mouseDoubleClick(): StatusResponse
    @POST("desktop/mouse/scroll")
    suspend fun mouseScroll(@Query("clicks") clicks: Int): StatusResponse
    @GET("desktop/mouse/position")
    suspend fun getMousePosition(): StatusResponse

    // Desktop: Keyboard
    @POST("desktop/keyboard/type")
    suspend fun keyboardType(@Body request: KeyTextRequest): StatusResponse
    @POST("desktop/keyboard/press")
    suspend fun keyboardPress(@Body request: KeyPressRequest): StatusResponse
    @POST("desktop/keyboard/hotkey")
    suspend fun keyboardHotkey(@Body keys: List<String>): StatusResponse

    // Desktop: Screenshot
    @POST("desktop/screenshot")
    suspend fun takeScreenshot(): StatusResponse
    @GET("desktop/screenshot")
    suspend fun getScreenshot(): ScreenshotResponse

    // Desktop: Power
    @POST("desktop/power/shutdown")
    suspend fun shutdown(@Body request: PowerRequest): PowerResponse
    @POST("desktop/power/restart")
    suspend fun restart(@Body request: PowerRequest): PowerResponse
    @POST("desktop/power/lock")
    suspend fun lock(): PowerResponse
    @POST("desktop/power/sleep")
    suspend fun sleep(@Body request: PowerRequest): PowerResponse
    @POST("desktop/power/hibernate")
    suspend fun hibernate(@Body request: PowerRequest): PowerResponse
    @POST("desktop/power/logoff")
    suspend fun logoff(@Body request: PowerRequest): PowerResponse
    @POST("desktop/power/abort-shutdown")
    suspend fun abortShutdown(): PowerResponse

    // Files
    @POST("files/delete")
    suspend fun deleteFile(@Body request: FileDeleteRequest): PowerResponse

    // Desktop: Approvals
    @GET("desktop/approvals")
    suspend fun getApprovals(): ApprovalResponse
    @POST("desktop/approvals/{id}/approve")
    suspend fun approveAction(@Path("id") id: String): StatusResponse
    @POST("desktop/approvals/{id}/deny")
    suspend fun denyAction(@Path("id") id: String): StatusResponse

    // Windows
    @GET("windows")
    suspend fun listWindows(): StatusResponse
    @POST("windows/focus")
    suspend fun focusWindow(@Body request: Map<String, String>): StatusResponse
    @POST("windows/close")
    suspend fun closeWindow(@Body request: Map<String, String>): StatusResponse
    @POST("windows/minimize")
    suspend fun minimizeWindow(@Body request: Map<String, String>): StatusResponse
    @POST("windows/maximize")
    suspend fun maximizeWindow(@Body request: Map<String, String>): StatusResponse

    // Files
    @GET("files/browse")
    suspend fun browseFiles(@Query("path") path: String? = null): FileBrowseResponse
    @GET("files/search")
    suspend fun searchFiles(@Query("query") query: String): FileSearchResponse
    @GET("files/special-folders")
    suspend fun getSpecialFolders(): Map<String, String>
    @GET("files/drives")
    suspend fun getDrives(): FileSearchResponse

    // Applications
    @GET("desktop/applications/search")
    suspend fun searchApplications(@Query("query") query: String): List<AppInfo>
    @POST("desktop/applications/launch")
    suspend fun launchApplication(@Body request: Map<String, String>): StatusResponse
    @POST("desktop/applications/close")
    suspend fun closeApplication(@Body request: Map<String, String>): StatusResponse

    @GET("desktop/applications/processes")
    suspend fun listProcesses(): List<Map<String, Any>>

    // Files
    @POST("desktop/files/rename")
    suspend fun renameFile(@Body request: FileRenameRequest): PowerResponse

    @POST("desktop/files/move")
    suspend fun moveFile(@Body request: FileMoveRequest): PowerResponse

    @POST("desktop/files/copy")
    suspend fun copyFile(@Body request: FileCopyRequest): PowerResponse

    // Notifications
    @GET("notifications")
    suspend fun getNotifications(): NotificationsResponse
    @POST("notifications/read")
    suspend fun markNotificationsRead(@Body request: NotificationsReadRequest): PowerResponse
    @GET("notifications/preferences")
    suspend fun getNotificationPrefs(): NotificationPrefsResponse
    @PUT("notifications/preferences")
    suspend fun updateNotificationPrefs(@Body request: NotificationPrefsRequest): NotificationPrefsResponse
    @GET("remote/wake-word")
    suspend fun getWakeWord(): WakeWordResponse
    @PUT("remote/wake-word")
    suspend fun updateWakeWord(@Body request: WakeWordRequest): WakeWordResponse

    // Automation
    @GET("automation/rules")
    suspend fun getAutomationRules(): AutomationRulesResponse

    // Media
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

    // Remote Control: System Status & Service Management
    @GET("remote/status")
    suspend fun getRemoteSystemStatus(): RemoteSystemStatusResponse

    @POST("remote/start")
    suspend fun startService(@Body request: RemoteStartRequest): RemoteStartResponse

    @POST("remote/wol")
    suspend fun wakeOnLan(@Body request: WolRequest): WolResponse
}

// ═══════════════════════════════════════════════════════════════════════
// Request / Response Models (matching DASH backend JSON contracts)
// ═══════════════════════════════════════════════════════════════════════

data class LoginRequest(val email: String, val password: String)
data class AuthResponse(val access_token: String, val refresh_token: String, val token_type: String = "bearer")

data class StatusResponse(val status: String = "ok", val details: Map<String, Any> = emptyMap())
data class PowerResponse(val summary: String = "")

// Memory
data class MemoryItem(val id: String = "", val content: String = "", val type: String = "", val pinned: Boolean = false, val created_at: String = "", val tags: List<String> = emptyList())
data class MemoriesResponse(val memories: List<MemoryItem> = emptyList(), val count: Int = 0)
data class CreateMemoryRequest(val content: String, val type: String = "custom", val tags: List<String> = emptyList())
data class MemoryResponse(val memory: MemoryItem? = null, val status: String = "ok")

// Projects
data class ProjectItem(val id: String = "", val name: String = "", val description: String = "", val path: String = "", val language: String = "", val created_at: String = "", val updated_at: String = "")
data class ProjectsResponse(val projects: List<ProjectItem> = emptyList(), val count: Int = 0)
data class CreateProjectRequest(val name: String, val description: String = "", val path: String = "", val language: String = "")
data class ProjectResponse(val project: ProjectItem? = null, val status: String = "ok")

// Conversations
data class Conversation(val id: String = "", val title: String = "", val created_at: String = "", val updated_at: String = "")

// Desktop: Volume
data class VolumeSetRequest(val level: Int)
data class MuteRequest(val muted: Boolean = true)
data class VolumeResponse(val volume: Float = 0f, val muted: Boolean = false, val summary: String = "")

// Desktop: Brightness
data class BrightnessResponse(val brightness: Int = 0, val summary: String = "")
data class BrightnessSetRequest(val level: Int)

// Desktop: Clipboard
data class ClipboardWriteRequest(val text: String)
data class ClipboardResponse(val text: String = "", val summary: String = "")

// Desktop: Mouse
data class MouseMoveRequest(val x: Int, val y: Int)
data class MouseClickRequest(val button: String = "left", val x: Int? = null, val y: Int? = null)

// Desktop: Keyboard
data class KeyTextRequest(val text: String)
data class KeyPressRequest(val key: String)

// Desktop: Power
data class PowerRequest(val force: Boolean = true, val timeout: Int = 30, val approval_id: String? = null)

data class TypeTextRequest(val text: String)
data class PressKeyRequest(val key: String)
data class HotkeyRequest(val keys: List<String>)
data class ClipboardData(val text: String = "")
data class FileDeleteRequest(val path: String, val permanent: Boolean = false)
data class FileRenameRequest(val oldPath: String, val newPath: String)
data class FileMoveRequest(val source: String, val destination: String)
data class FileCopyRequest(val source: String, val destination: String)

// Desktop: Approvals
data class ApprovalItem(val id: String = "", val action_type: String = "", val description: String = "", val created_at: String = "")
data class ApprovalResponse(val approvals: List<ApprovalItem> = emptyList(), val count: Int = 0)

// Screenshot
data class ScreenshotResponse(val status: String = "ok", val image_base64: String = "", val width: Int = 0, val height: Int = 0)

// Notifications
data class NotificationItem(val id: String = "", val title: String = "", val text: String = "", val source: String = "", val timestamp: Long = 0, val read: Boolean = false)
data class NotificationsResponse(val notifications: List<NotificationItem> = emptyList(), val count: Int = 0, val unread_count: Int = 0)
data class NotificationsReadRequest(val ids: List<String>? = null, val all: Boolean = false)
data class NotificationPrefsResponse(val process: Boolean = true, val error: Boolean = true, val system: Boolean = true)
data class NotificationPrefsRequest(val process: Boolean? = null, val error: Boolean? = null, val system: Boolean? = null)
data class WakeWordResponse(val phrase: String = "Hey DASH")
data class WakeWordRequest(val phrase: String)

// Automation
data class AutomationRule(val id: String = "", val name: String = "", val description: String = "", val enabled: Boolean = false, val trigger: String = "", val action: String = "")
data class AutomationRulesResponse(val rules: List<AutomationRule> = emptyList(), val count: Int = 0)

// Media
data class MediaStatus(val is_playing: Boolean = false, val title: String = "", val artist: String = "", val album: String = "")
data class MediaStatusResponse(val status: String = "ok", val media: MediaStatus = MediaStatus())

// Files
data class FileItem(val name: String = "", val path: String = "", val type: String = "file", val size: Long = 0, val modified: String = "", val extension: String = "")
data class FileBrowseResponse(val path: String = "", val files: List<FileItem> = emptyList(), val parent: String? = null)
data class FileSearchResponse(val files: List<FileItem> = emptyList(), val count: Int = 0)

// Applications
data class AppInfo(val name: String = "", val path: String = "", val icon: String? = null, val pid: Int? = null)

// Remote Control
data class RemoteServiceStatus(val name: String = "", val running: Boolean = false, val healthy: Boolean = false, val detail: String = "")
data class RemoteSystemStatusResponse(
    val backend: RemoteServiceStatus = RemoteServiceStatus(),
    val ollama: RemoteServiceStatus = RemoteServiceStatus(),
    val qwen: RemoteServiceStatus = RemoteServiceStatus(),
    val desktop: RemoteServiceStatus = RemoteServiceStatus(),
    val overall: String = "offline"
)
data class RemoteStartRequest(val service: String = "all", val force: Boolean = false)
data class RemoteStartResponse(val success: Boolean = false, val message: String = "", val status: RemoteSystemStatusResponse = RemoteSystemStatusResponse())
data class WolRequest(val mac_address: String = "", val broadcast: String? = null, val count: Int = 3)
data class WolResponse(val summary: String = "", val mac_address: String = "", val packets_sent: Int = 0, val errors: List<String> = emptyList())
