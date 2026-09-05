package com.example.data.connection

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.example.data.api.DashApiService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Handles notification action button clicks (Lock, Sleep, Volume, etc.)
 * without opening the app — runs in background via the foreground service.
 */
class DashNotificationReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        Log.i(TAG, "Notification action: $action")

        CoroutineScope(Dispatchers.IO).launch {
            try {
                when (action) {
                    ACTION_LOCK -> {
                        DashApiService.lock()
                        updateNotification(context, "PC Locked")
                    }
                    ACTION_SLEEP -> {
                        DashApiService.sleep()
                        updateNotification(context, "PC Sleeping...")
                    }
                    ACTION_VOLUME_UP -> {
                        val vol = DashApiService.getVolume()
                        val newLevel = (vol.volume.toInt() + 10).coerceAtMost(100)
                        DashApiService.setVolume(newLevel)
                        updateNotification(context, "Volume: $newLevel%")
                    }
                    ACTION_VOLUME_DOWN -> {
                        val vol = DashApiService.getVolume()
                        val newLevel = (vol.volume.toInt() - 10).coerceAtLeast(0)
                        DashApiService.setVolume(newLevel)
                        updateNotification(context, "Volume: $newLevel%")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Action $action failed: ${e.message}")
                updateNotification(context, "Action failed: ${e.message}")
            }
        }
    }

    private fun updateNotification(context: Context, text: String) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(
            DashForegroundService.NOTIFICATION_ID,
            DashForegroundService.buildNotificationStatic(context, text)
        )
    }

    companion object {
        private const val TAG = "DashNotifReceiver"
        const val ACTION_LOCK = "com.example.dash.LOCK"
        const val ACTION_SLEEP = "com.example.dash.SLEEP"
        const val ACTION_VOLUME_UP = "com.example.dash.VOLUME_UP"
        const val ACTION_VOLUME_DOWN = "com.example.dash.VOLUME_DOWN"
    }
}
