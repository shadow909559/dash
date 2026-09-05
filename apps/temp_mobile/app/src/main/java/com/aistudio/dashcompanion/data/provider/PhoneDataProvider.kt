package com.aistudio.dashcompanion.data.provider

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Environment
import android.os.StatFs
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.hardware.camera2.CameraManager
import android.content.pm.PackageManager
import android.content.ClipboardManager
import android.media.AudioManager
import android.app.NotificationManager
import android.os.Build
import android.content.pm.ApplicationInfo
import android.media.session.MediaSessionManager
import android.service.notification.StatusBarNotification
import android.media.MediaMetadata
import android.media.session.PlaybackState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File

class PhoneDataProvider(private val context: Context) {

    private val _phoneState = MutableStateFlow<PhoneState>(PhoneState())
    val phoneState: StateFlow<PhoneState> = _phoneState.asStateFlow()

    private val clipboardManager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    private val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private val mediaSessionManager = context.getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager

    private var _flashlightEnabled = false

    fun updatePhoneData() {
        _phoneState.value = PhoneState(
            battery = getBatteryInfo(),
            storage = getStorageInfo(),
            network = getNetworkInfo(),
            clipboard = getClipboardText(),
            volume = getVolumeInfo(),
            flashlight = getFlashlightState(),
            notificationsEnabled = areNotificationsEnabled(),
            activeMedia = getActiveMediaInfo(),
            timestamp = System.currentTimeMillis()
        )
    }

    private fun getBatteryInfo(): BatteryInfo {
        val batteryStatus = IntentFilter(Intent.ACTION_BATTERY_CHANGED).let {
            context.registerReceiver(null, it)
        }
        val level = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val pct = if (level != -1 && scale != -1) level * 100 / scale.toFloat() else 0f
        val status = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        val health = batteryStatus?.getIntExtra(BatteryManager.EXTRA_HEALTH, -1) ?: -1
        val healthStatus = when (health) {
            BatteryManager.BATTERY_HEALTH_GOOD -> "good"
            BatteryManager.BATTERY_HEALTH_OVERHEAT -> "overheat"
            BatteryManager.BATTERY_HEALTH_DEAD -> "dead"
            BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "over_voltage"
            BatteryManager.BATTERY_HEALTH_UNSPECIFIED_FAILURE -> "failure"
            else -> "unknown"
        }
        return BatteryInfo(
            level = pct.toInt(), isCharging = isCharging, health = healthStatus,
            temperature = batteryStatus?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)?.toFloat()?.div(10f) ?: 0f,
            voltage = batteryStatus?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0)?.toFloat()?.div(1000f) ?: 0f,
            technology = batteryStatus?.getStringExtra(BatteryManager.EXTRA_TECHNOLOGY) ?: "unknown"
        )
    }

    private fun getStorageInfo(): StorageInfo {
        val state = Environment.getExternalStorageState()
        if (Environment.MEDIA_MOUNTED != state) return StorageInfo()
        val internal = getStorageStats(Environment.getDataDirectory())
        val external = if (Environment.isExternalStorageEmulated()) internal
        else getStorageStats(Environment.getExternalStorageDirectory())
        return StorageInfo(
            totalBytes = internal.totalBytes + external.totalBytes,
            usedBytes = internal.usedBytes + external.usedBytes,
            freeBytes = internal.freeBytes + external.freeBytes,
            usedPercent = if ((internal.totalBytes + external.totalBytes) > 0)
                ((internal.usedBytes + external.usedBytes) * 100 / (internal.totalBytes + external.totalBytes)).toInt() else 0
        )
    }

    private fun getStorageStats(dir: File): StorageStats {
        val stat = StatFs(dir.path)
        return StorageStats(stat.totalBytes, stat.totalBytes - stat.availableBytes, stat.availableBytes)
    }

    private fun getNetworkInfo(): NetworkInfo {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val activeNetwork = connectivityManager.activeNetworkInfo
        val isConnected = activeNetwork?.isConnected == true
        val type = when (activeNetwork?.type) {
            ConnectivityManager.TYPE_WIFI -> "wifi"
            ConnectivityManager.TYPE_MOBILE -> "mobile"
            ConnectivityManager.TYPE_ETHERNET -> "ethernet"
            else -> "unknown"
        }
        val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val wifiInfo = wifiManager.connectionInfo
        val ssid = if (type == "wifi" && wifiInfo != null) wifiInfo.ssid?.replace("\"", "") ?: "unknown" else "unknown"
        return NetworkInfo(isConnected = isConnected, type = type, ssid = ssid,
            isMetered = try { if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) connectivityManager.isActiveNetworkMetered else false } catch (e: Exception) { false },
            signalStrength = if (type == "wifi" && wifiInfo != null) WifiManager.calculateSignalLevel(wifiInfo.rssi, 100) else 0)
    }

    fun getClipboardText(): String {
        return try { clipboardManager.primaryClip?.let { if (it.itemCount > 0) it.getItemAt(0).text?.toString() ?: "" else "" } ?: "" }
        catch (e: Exception) { "" }
    }

    private fun getVolumeInfo(): VolumeInfo {
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val current = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        return VolumeInfo(volume = if (max > 0) (current * 100) / max else 0,
            isMuted = audioManager.isStreamMute(AudioManager.STREAM_MUSIC), maxVolume = max)
    }

    private fun getFlashlightState(): Boolean {
        return _flashlightEnabled
    }

    private fun isFlashlightAvailable(): Boolean {
        return context.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_FLASH)
    }

    private fun areNotificationsEnabled(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) notificationManager.areNotificationsEnabled() else true
    }

    fun setClipboardText(text: String) {
        try {
            val clipData = android.content.ClipData.newPlainText("DASH", text)
            clipboardManager.setPrimaryClip(clipData)
            updatePhoneData()
        } catch (e: Exception) { }
    }

    fun setVolume(volume: Int) {
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, (volume * max) / 100, 0)
        updatePhoneData()
    }

    fun toggleMute() {
        audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_TOGGLE_MUTE, 0)
        updatePhoneData()
    }

    fun setFlashlight(enabled: Boolean): Boolean {
        if (!isFlashlightAvailable()) return false
        return try {
            val cameraId = cameraManager.cameraIdList[0]
            cameraManager.setTorchMode(cameraId, enabled)
            _flashlightEnabled = enabled
            updatePhoneData()
            true
        } catch (e: Exception) { false }
    }

    fun getInstalledApps(): List<AppInfo> {
        val pm = context.packageManager
        val apps = mutableListOf<AppInfo>()
        try {
            val packages = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getInstalledApplications(PackageManager.ApplicationInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION") pm.getInstalledApplications(0)
            }
            for (app in packages) {
                if (app.flags and ApplicationInfo.FLAG_SYSTEM == 0 || (app.flags and ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0) {
                    apps.add(AppInfo(
                        packageName = app.packageName,
                        name = pm.getApplicationLabel(app).toString(),
                        icon = app.icon,
                        isSystemApp = (app.flags and ApplicationInfo.FLAG_SYSTEM) != 0
                    ))
                }
            }
        } catch (e: Exception) { }
        return apps.sortedBy { it.name }
    }

    fun getActiveMediaInfo(): MediaInfo {
        try {
            val controllers = mediaSessionManager.getActiveSessions(null)
            if (controllers.isNotEmpty()) {
                val controller = controllers[0]
                val metadata = controller.metadata
                val playbackState = controller.playbackState
                return MediaInfo(
                    isPlaying = playbackState?.state == PlaybackState.STATE_PLAYING,
                    title = metadata?.getString(MediaMetadata.METADATA_KEY_TITLE) ?: "",
                    artist = metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: "",
                    album = metadata?.getString(MediaMetadata.METADATA_KEY_ALBUM) ?: "",
                    duration = metadata?.getLong(MediaMetadata.METADATA_KEY_DURATION) ?: 0,
                    position = playbackState?.position ?: 0,
                    packageName = controller.packageName
                )
            }
        } catch (e: Exception) { }
        return MediaInfo()
    }

    fun getActiveNotifications(): List<NotificationItem> {
        val items = mutableListOf<NotificationItem>()
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val sbn = notificationManager.activeNotifications
                for (n in sbn) {
                    val extras = n.notification.extras
                    items.add(NotificationItem(
                        packageName = n.packageName,
                        key = n.key,
                        title = extras.getCharSequence("android.title")?.toString() ?: "",
                        text = extras.getCharSequence("android.text")?.toString() ?: "",
                        timestamp = n.postTime
                    ))
                }
            }
        } catch (e: Exception) { }
        return items
    }
}

data class PhoneState(
    val battery: BatteryInfo = BatteryInfo(),
    val storage: StorageInfo = StorageInfo(),
    val network: NetworkInfo = NetworkInfo(),
    val clipboard: String = "",
    val volume: VolumeInfo = VolumeInfo(),
    val flashlight: Boolean = false,
    val notificationsEnabled: Boolean = true,
    val activeMedia: MediaInfo = MediaInfo(),
    val timestamp: Long = System.currentTimeMillis()
)

data class BatteryInfo(
    val level: Int = 0, val isCharging: Boolean = false, val health: String = "unknown",
    val temperature: Float = 0f, val voltage: Float = 0f, val technology: String = "unknown"
)

data class StorageInfo(val totalBytes: Long = 0, val usedBytes: Long = 0, val freeBytes: Long = 0, val usedPercent: Int = 0)
data class NetworkInfo(val isConnected: Boolean = false, val type: String = "unknown", val ssid: String = "unknown",
                       val isMetered: Boolean = false, val signalStrength: Int = 0)
data class VolumeInfo(val volume: Int = 0, val isMuted: Boolean = false, val maxVolume: Int = 100)
data class StorageStats(val totalBytes: Long, val usedBytes: Long, val freeBytes: Long)
data class AppInfo(val packageName: String = "", val name: String = "", val icon: Int = 0, val isSystemApp: Boolean = false)
data class MediaInfo(val isPlaying: Boolean = false, val title: String = "", val artist: String = "",
                     val album: String = "", val duration: Long = 0, val position: Long = 0,
                     val packageName: String = "")
data class NotificationItem(val packageName: String = "", val key: String = "", val title: String = "",
                            val text: String = "", val timestamp: Long = 0)
