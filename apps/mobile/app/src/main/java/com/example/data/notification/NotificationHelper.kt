package com.example.data.notification

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.example.R
import com.example.MainActivity

/**
 * Shows Android system notifications when DASH backend pushes desktop notifications.
 * Users will see Windows notifications as phone notifications.
 * Tapping a notification opens the app.
 */
object NotificationHelper {

    private const val CHANNEL_ID = "dash_desktop_notifications"
    private const val CHANNEL_NAME = "Desktop Notifications"
    private var nextId = 1000

    fun init(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Notifications forwarded from Windows desktop"
            enableVibration(true)
        }
        nm.createNotificationChannel(channel)
    }

    fun showDesktopNotification(context: Context, title: String, message: String) {
        // PendingIntent to open app when notification is tapped
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("notification_title", title)
            putExtra("notification_message", message)
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            nextId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("\uD83D\uDDA5\uFE0F $title")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        nm.notify(nextId++, notification)
    }
}
