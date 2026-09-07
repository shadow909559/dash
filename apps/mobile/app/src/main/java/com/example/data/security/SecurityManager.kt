package com.example.data.security

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Security Manager — Keystore-backed encrypted storage for the DASH device token
 * and server configuration. Sensitive values are never written to plaintext.
 */
object SecurityManager {
    private const val TAG = "SecurityManager"
    private const val PREFS_NAME = "dash_security"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_AUTH_TOKEN = "auth_token"
    private const val KEY_SERVER_IP = "server_ip"
    private const val KEY_SERVER_PORT = "server_port"
    private const val KEY_DEVICE_TOKEN = "device_token"

    @Volatile
    private var encryptedPrefs: SharedPreferences? = null

    fun initialize(context: Context) {
        ensureDeviceId(context)
    }

    // ─── Auth Token ───

    fun saveAuthToken(context: Context, token: String) {
        try {
            getEncryptedSharedPreferences(context)
                .edit()
                .putString(KEY_AUTH_TOKEN, token)
                .apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store auth token", e)
        }
    }

    fun getAuthToken(context: Context): String? {
        return try {
            getEncryptedSharedPreferences(context).getString(KEY_AUTH_TOKEN, null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read auth token", e)
            null
        }
    }

    // ─── Device Token (for companion pairing) ───

    fun saveDeviceToken(context: Context, token: String) {
        try {
            getEncryptedSharedPreferences(context)
                .edit()
                .putString(KEY_DEVICE_TOKEN, token)
                .apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store device token", e)
        }
    }

    fun getDeviceToken(context: Context): String? {
        return try {
            getEncryptedSharedPreferences(context).getString(KEY_DEVICE_TOKEN, null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read device token", e)
            null
        }
    }

    // ─── Server Configuration ───

    fun saveServerConfig(context: Context, ip: String, port: String) {
        try {
            getEncryptedSharedPreferences(context)
                .edit()
                .putString(KEY_SERVER_IP, ip)
                .putString(KEY_SERVER_PORT, port)
                .apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store server config", e)
        }
    }

    fun getServerIp(context: Context): String? {
        return try {
            getEncryptedSharedPreferences(context).getString(KEY_SERVER_IP, null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read server IP", e)
            null
        }
    }

    fun getServerPort(context: Context): String? {
        return try {
            getEncryptedSharedPreferences(context).getString(KEY_SERVER_PORT, null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read server port", e)
            null
        }
    }

    /** Check if server configuration has been saved (i.e. user has paired before). */
    fun hasServerConfig(context: Context): Boolean {
        return try {
            val prefs = getEncryptedSharedPreferences(context)
            !prefs.getString(KEY_SERVER_IP, null).isNullOrBlank()
        } catch (e: Exception) {
            false
        }
    }

    // ─── Clear ───

    fun clearSensitiveData(context: Context) {
        getSharedPreferences(context).edit().clear().apply()
        try {
            getEncryptedSharedPreferences(context).edit().clear().apply()
            encryptedPrefs = null
        } catch (e: Exception) {
            Log.e(TAG, "Failed to clear encrypted prefs", e)
        }
    }

    fun getDeviceId(context: Context): String {
        return getSharedPreferences(context).getString(KEY_DEVICE_ID, "unknown") ?: "unknown"
    }

    // ─── Internal ───

    private fun ensureDeviceId(context: Context) {
        val prefs = getSharedPreferences(context)
        if (!prefs.contains(KEY_DEVICE_ID)) {
            val androidId = android.provider.Settings.Secure.getString(
                context.contentResolver, android.provider.Settings.Secure.ANDROID_ID
            ) ?: "unknown_device"
            val hash = java.security.MessageDigest.getInstance("SHA-256")
                .digest(androidId.toByteArray())
            val id = Base64.encodeToString(hash, Base64.NO_WRAP).substring(0, 16)
            prefs.edit().putString(KEY_DEVICE_ID, id).apply()
        }
    }

    private fun getSharedPreferences(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    private fun getEncryptedSharedPreferences(context: Context): SharedPreferences {
        encryptedPrefs?.let { return it }
        synchronized(this) {
            encryptedPrefs?.let { return it }
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            val prefs = EncryptedSharedPreferences.create(
                context,
                "dash_secure_prefs",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
            encryptedPrefs = prefs
            return prefs
        }
    }
}
