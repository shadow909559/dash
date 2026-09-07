package com.example.data.connection

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import com.example.MainActivity
import com.example.data.connection.DashNotificationReceiver
import com.example.data.audio.WakeWordDetector
import com.example.data.notification.NotificationChime
import com.example.data.audio.SttRecorder
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Foreground service that keeps the DASH WebSocket connection alive
 * even when the app is backgrounded or the screen is off.
 *
 * Prevents Android (especially OPPO/Realme/Huawei) from freezing
 * the app process, which would kill the WebSocket connection.
 */
class DashForegroundService : Service() {

    private var wifiLock: WifiManager.WifiLock? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        acquireLocks()
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification("Connected to DASH")
        startForeground(NOTIFICATION_ID, notification)
        Log.i(TAG, "Foreground service started — connection kept alive")

        // Observe connection state and update notification
        startStateObserver()

        // Start wake word detection if enabled
        if (WakeWordDetector.isWakeWordEnabled.value) {
            startWakeWordDetection()
        }

        return START_STICKY
    }

    override fun onDestroy() {
        WakeWordDetector.stopDetection()
        releaseLocks()
        Log.i(TAG, "Foreground service destroyed")
        super.onDestroy()
    }

    fun startWakeWordDetection() {
        WakeWordDetector.startDetection(serviceScope) {
            // Wake word detected — play chime so user knows DASH is listening
            Log.i(TAG, "Wake word detected — starting voice capture")
            try {
                // Play audible chime to acknowledge wake word
                NotificationChime.playLight()

                if (!SttRecorder.isRecording) {
                    SttRecorder.start()
                    // Auto-stop after 8 seconds of recording
                    serviceScope.launch {
                        kotlinx.coroutines.delay(8000)
                        if (SttRecorder.isRecording) {
                            val audio = SttRecorder.stop()
                            if (audio != null) {
                                WebSocketManager.sendVoiceStt(audio)
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start voice capture: ${e.message}")
            }
        }
    }

    fun stopWakeWordDetection() {
        WakeWordDetector.stopDetection()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "DASH Connection",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Keeps DASH connected to your PC"
            setShowBadge(false)
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        return buildNotificationStatic(this, text)
    }

    companion object {
        private const val TAG = "DashService"
        private const val CHANNEL_ID = "dash_connection"
        const val NOTIFICATION_ID = 1337

        fun buildNotificationStatic(context: Context, text: String): Notification {
            val pendingIntent = PendingIntent.getActivity(
                context, 0,
                Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                },
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            // Action button intents
            fun actionPendingIntent(action: String): PendingIntent {
                return PendingIntent.getBroadcast(
                    context, action.hashCode(),
                    Intent(context, DashNotificationReceiver::class.java).apply {
                        this.action = action
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
            }

            return Notification.Builder(context, CHANNEL_ID)
                .setContentTitle("DASH Active")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .addAction(
                    Notification.Action.Builder(
                        null, "Lock PC",
                        actionPendingIntent(DashNotificationReceiver.ACTION_LOCK)
                    ).build()
                )
                .addAction(
                    Notification.Action.Builder(
                        null, "Sleep",
                        actionPendingIntent(DashNotificationReceiver.ACTION_SLEEP)
                    ).build()
                )
                .addAction(
                    Notification.Action.Builder(
                        null, "Vol-",
                        actionPendingIntent(DashNotificationReceiver.ACTION_VOLUME_DOWN)
                    ).build()
                )
                .addAction(
                    Notification.Action.Builder(
                        null, "Vol+",
                        actionPendingIntent(DashNotificationReceiver.ACTION_VOLUME_UP)
                    ).build()
                )
                .build()
        }

        fun start(context: Context) {
            try {
                val intent = Intent(context, DashForegroundService::class.java)
                context.startForegroundService(intent)
            } catch (e: Exception) {
                android.util.Log.w("DASHService", "Cannot start foreground service: ${e.message}")
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, DashForegroundService::class.java))
        }
    }

    private fun startStateObserver() {
        Thread {
            var lastState: WebSocketManager.ConnectionState? = null
            while (!Thread.currentThread().isInterrupted) {
                val state = WebSocketManager.connectionState.value
                if (state != lastState) {
                    lastState = state
                    val text = when (state) {
                        WebSocketManager.ConnectionState.Authenticated -> "Connected to DASH"
                        WebSocketManager.ConnectionState.Connected -> "Authenticating..."
                        WebSocketManager.ConnectionState.AuthFailed -> "Authentication failed"
                        WebSocketManager.ConnectionState.Disconnected -> "Disconnected — reconnecting..."
                        WebSocketManager.ConnectionState.DisconnectedError -> "Connection error — retrying..."
                        null -> "Connecting..."
                    }
                    val manager = getSystemService(NotificationManager::class.java)
                    manager.notify(NOTIFICATION_ID, buildNotification(text))
                }
                Thread.sleep(2000)
            }
        }.apply { isDaemon = true; start() }
    }

    private fun acquireLocks() {
        try {
            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "DASH:WebSocketLock").apply {
                acquire()
            }
            Log.i(TAG, "WiFi lock acquired")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acquire WiFi lock", e)
        }

        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "DASH:ConnectionLock"
            ).apply {
                acquire()
            }
            Log.i(TAG, "Wake lock acquired")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acquire wake lock", e)
        }
    }

    private fun releaseLocks() {
        try { wifiLock?.release() } catch (_: Exception) {}
        try { wakeLock?.release() } catch (_: Exception) {}
        wifiLock = null
        wakeLock = null
    }

}
