package com.example.conceirge

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.example.conceirge.data.UrlStore
import com.example.conceirge.data.models.AppSettingsUpdate
import com.example.conceirge.data.network.RetrofitInstance
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class ConciergeFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        val url = UrlStore.getUrl(this) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                RetrofitInstance.create(url).updateSettings(AppSettingsUpdate(fcm_token = token))
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val notification = message.notification ?: return
        val channelId = "downloads"
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager

        val channel = NotificationChannel(channelId, "Downloads", NotificationManager.IMPORTANCE_DEFAULT)
        manager.createNotificationChannel(channel)

        val libraryItemId = message.data["library_item_id"]?.takeIf { it.isNotBlank() }
        val navigateTo = if (libraryItemId != null) "library/$libraryItemId" else "home"

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("navigate_to", navigateTo)
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notif = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(notification.title)
            .setContentText(notification.body)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        manager.notify(System.currentTimeMillis().toInt(), notif)
    }
}
