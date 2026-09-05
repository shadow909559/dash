package com.aistudio.dashcompanion.data.notification

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aistudio.dashcompanion.R
import com.aistudio.dashcompanion.presentation.MainActivity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Desktop Notification Manager
 * Handles notifications for important desktop events
 */
object DesktopNotificationManager {
    private const val TAG = "DesktopNotification"
    private const val CHANNEL_ID = "dash_desktop_events"
    private const val CHANNEL_NAME = "DASH Desktop Events"
    private const val CHANNEL_DESCRIPTION = "Notifications from DASH Desktop"
    
    enum class NotificationType {
        TASK_COMPLETED,
        DESKTOP_DISCONNECTED,
        UPDATE_AVAILABLE,
        AUTOMATION_COMPLETED,
        APPROVAL_REQUIRED,
        COMMAND_FAILED,
        VOICE_COMMAND
    }
    
    data class DesktopNotification(
        val id: Int,
        val type: NotificationType,
        val title: String,
        val message: String,
        val timestamp: Long = System.currentTimeMillis(),
        val dismissible: Boolean = true
    )
    
    private val _notifications = MutableStateFlow<List<DesktopNotification>>(emptyList())
    val notifications: StateFlow<List<DesktopNotification>> = _notifications.asStateFlow()
    
    private var notificationIdCounter = 1000
    private var context: Context? = null
    
    /**
     * Initialize with context
     */
    fun setContext(context: Context) {
        this.context = context
        createNotificationChannel()
    }
    
    /**
     * Create notification channel
     */
    private fun createNotificationChannel() {
        val ctx = context ?: return
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = CHANNEL_DESCRIPTION
                enableLights(true)
                enableVibration(true)
            }
            
            val notificationManager = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    /**
     * Show notification
     */
    fun showNotification(
        type: NotificationType,
        title: String,
        message: String,
        dismissible: Boolean = true
    ) {
        val ctx = context ?: return
        
        val notificationId = notificationIdCounter++
        val notification = DesktopNotification(
            id = notificationId,
            type = type,
            title = title,
            message = message,
            dismissible = dismissible
        )
        
        // Add to notification list
        _notifications.value = _notifications.value + notification
        
        // Show system notification
        val systemNotification = createSystemNotification(notification)
        val notificationManager = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(notificationId, systemNotification)
        
        Log.d(TAG, "Notification shown: $title - $message")
    }
    
    /**
     * Create system notification
     */
    private fun createSystemNotification(notification: DesktopNotification): Notification {
        val ctx = context ?: return Notification()
        
        val intent = Intent(ctx, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        
        val pendingIntent = PendingIntent.getActivity(
            ctx,
            notification.id,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        
        val builder = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setContentTitle(notification.title)
            .setContentText(notification.message)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentIntent(pendingIntent)
            .setAutoCancel(notification.dismissible)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
        
        return builder.build()
    }
    
    /**
     * Dismiss notification
     */
    fun dismissNotification(notificationId: Int) {
        val ctx = context ?: return
        
        // Remove from list
        _notifications.value = _notifications.value.filter { it.id != notificationId }
        
        // Cancel system notification
        val notificationManager = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.cancel(notificationId)
        
        Log.d(TAG, "Notification dismissed: $notificationId")
    }
    
    /**
     * Clear all notifications
     */
    fun clearAllNotifications() {
        val ctx = context ?: return
        
        _notifications.value = emptyList()
        
        val notificationManager = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.cancelAll()
        
        Log.d(TAG, "All notifications cleared")
    }
    
    /**
     * Convenience methods for common notifications
     */
    fun notifyTaskCompleted(taskName: String) {
        showNotification(
            type = NotificationType.TASK_COMPLETED,
            title = "Task Completed",
            message = "$taskName has been completed on your desktop"
        )
    }
    
    fun notifyDesktopDisconnected(reason: String? = null) {
        showNotification(
            type = NotificationType.DESKTOP_DISCONNECTED,
            title = "Desktop Disconnected",
            message = reason ?: "Connection to DASH Desktop has been lost"
        )
    }
    
    fun notifyUpdateAvailable(version: String) {
        showNotification(
            type = NotificationType.UPDATE_AVAILABLE,
            title = "Update Available",
            message = "DASH Desktop version $version is available"
        )
    }
    
    fun notifyAutomationCompleted(automationName: String) {
        showNotification(
            type = NotificationType.AUTOMATION_COMPLETED,
            title = "Automation Completed",
            message = "$automationName has finished running"
        )
    }
    
    fun notifyApprovalRequired(action: String) {
        showNotification(
            type = NotificationType.APPROVAL_REQUIRED,
            title = "Approval Required",
            message = "Desktop approval needed for: $action",
            dismissible = false
        )
    }
    
    fun notifyCommandFailed(command: String, error: String) {
        showNotification(
            type = NotificationType.COMMAND_FAILED,
            title = "Command Failed",
            message = "Failed to execute '$command': $error"
        )
    }
    
    fun notifyVoiceCommand(text: String) {
        showNotification(
            type = NotificationType.VOICE_COMMAND,
            title = "Voice Command",
            message = "Executed: $text"
        )
    }
    
    /**
     * Get notification count
     */
    fun getNotificationCount(): Int {
        return _notifications.value.size
    }
    
    /**
     * Get notifications by type
     */
    fun getNotificationsByType(type: NotificationType): List<DesktopNotification> {
        return _notifications.value.filter { it.type == type }
    }
}