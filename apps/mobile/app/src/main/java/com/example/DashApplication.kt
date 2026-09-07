package com.example

import android.app.Application
import android.util.Log
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import com.example.data.config.AppConfig
import com.example.data.security.SecurityManager
import com.example.data.connection.AutoConnectManager
import com.example.data.connection.DashForegroundService
import com.example.data.websocket.WebSocketManager
import com.example.ui.theme.ThemePreference
import com.example.ui.theme.AccentColorPreference
import com.example.ui.components.HapticPreference
import com.example.data.notification.NotificationSoundPreference
import com.example.data.audio.WakeWordDetector
import com.example.ui.components.ConversationMode

/**
 * DASH Application — initialises global singletons on startup.
 * Restores persisted server config and token so the app auto-connects.
 */
class DashApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        instance = this
        SecurityManager.initialize(this)

        // Restore all persisted configuration (server IP, port, device token)
        AppConfig.restoreFromStorage(this)

        ThemePreference.init(this)
        AccentColorPreference.init(this)
        HapticPreference.init(this)
        NotificationSoundPreference.init(this)
        WakeWordDetector.init(this)
        ConversationMode.init(this)
        WebSocketManager.init(this)
        AutoConnectManager.start(this)

        // Register with cloud relay (for hybrid WoL + status)
        GlobalScope.launch(Dispatchers.IO) {
            try {
                AutoConnectManager.registerWithCloudRelay()
            } catch (_: Exception) {}
        }

        // Foreground service is started from MainActivity after app is in foreground
        // (Android 12+ requires foreground context to start foreground services)

        Log.i(TAG, "DASH initialized — server=${AppConfig.SERVER_IP}:${AppConfig.SERVER_PORT}, " +
                "authenticated=${AppConfig.isAuthenticated}")
    }

    companion object {
        private const val TAG = "DASHApp"
        var instance: DashApplication? = null
            private set
    }
}
