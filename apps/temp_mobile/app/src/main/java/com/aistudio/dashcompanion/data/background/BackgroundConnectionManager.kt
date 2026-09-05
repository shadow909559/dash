package com.aistudio.dashcompanion.data.background

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aistudio.dashcompanion.R
import com.aistudio.dashcompanion.data.connection.ConnectionStateManager
import com.aistudio.dashcompanion.data.monitor.DesktopStatusMonitor
import com.aistudio.dashcompanion.data.websocket.EnhancedWebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Background Connection Service
 * Maintains WebSocket connection when app is in background
 */
class BackgroundConnectionService : Service() {
    private val TAG = "BackgroundConnection"
    private val NOTIFICATION_CHANNEL_ID = "dash_connection"
    private val NOTIFICATION_ID = 1001
    
    private val serviceScope = CoroutineScope(Dispatchers.IO)
    private var monitoringJob: Job? = null
    
    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "Background connection service created")
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification("Initializing..."))
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "Background connection service started")
        
        when (intent?.action) {
            ACTION_START -> startConnectionMonitoring()
            ACTION_STOP -> stopConnectionMonitoring()
            ACTION_UPDATE -> updateNotification()
        }
        
        return START_STICKY
    }
    
    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
    
    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "Background connection service destroyed")
        stopConnectionMonitoring()
    }
    
    private fun startConnectionMonitoring() {
        monitoringJob?.cancel()
        
        monitoringJob = serviceScope.launch {
            while (true) {
                updateNotification()
                delay(5000) // Update every 5 seconds
            }
        }
    }
    
    private fun stopConnectionMonitoring() {
        monitoringJob?.cancel()
        monitoringJob = null
    }
    
    private fun updateNotification() {
        val statusMessage = ConnectionStateManager.getStatusMessage()
        val notification = createNotification(statusMessage)
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, notification)
    }
    
    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            "DASH Connection",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Shows connection status to DASH Desktop"
        }
        
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.createNotificationChannel(channel)
    }
    
    private fun createNotification(statusText: String): Notification {
        val intent = Intent(this, com.aistudio.dashcompanion.presentation.MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        
        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("DASH Desktop Connection")
            .setContentText(statusText)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
    
    companion object {
        const val ACTION_START = "com.aistudio.dashcompanion.START_CONNECTION"
        const val ACTION_STOP = "com.aistudio.dashcompanion.STOP_CONNECTION"
        const val ACTION_UPDATE = "com.aistudio.dashcompanion.UPDATE_CONNECTION"
        
        fun startService(context: Context) {
            val intent = Intent(context, BackgroundConnectionService::class.java).apply {
                action = ACTION_START
            }
            context.startForegroundService(intent)
        }
        
        fun stopService(context: Context) {
            val intent = Intent(context, BackgroundConnectionService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }
}

/**
 * Background Connection Manager
 * Manages connection lifecycle when app is in background
 */
object BackgroundConnectionManager {
    private const val TAG = "BackgroundConnectionMgr"
    
    private var isServiceRunning = false
    private var context: Context? = null
    
    /**
     * Initialize with context
     */
    fun setContext(context: Context) {
        this.context = context
    }
    
    /**
     * Start background connection service
     */
    fun startBackgroundService() {
        val ctx = context ?: return
        
        if (!isServiceRunning) {
            BackgroundConnectionService.startService(ctx)
            isServiceRunning = true
            Log.d(TAG, "Background connection service started")
        }
    }
    
    /**
     * Stop background connection service
     */
    fun stopBackgroundService() {
        val ctx = context ?: return
        
        if (isServiceRunning) {
            BackgroundConnectionService.stopService(ctx)
            isServiceRunning = false
            Log.d(TAG, "Background connection service stopped")
        }
    }
    
    /**
     * Handle app moving to background
     */
    fun onAppBackground() {
        Log.d(TAG, "App moved to background")
        
        // Keep connection alive but reduce activity
        // The background service will maintain the connection
        startBackgroundService()
    }
    
    /**
     * Handle app returning to foreground
     */
    fun onAppForeground() {
        Log.d(TAG, "App returned to foreground")
        
        // Refresh connection state
        EnhancedWebSocketManager.autoConnect()
        
        // Stop background service (app will handle connection)
        stopBackgroundService()
    }
    
    /**
     * Check if service is running
     */
    fun isServiceActive(): Boolean {
        return isServiceRunning
    }
}