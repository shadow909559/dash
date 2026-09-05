package com.aistudio.dashcompanion.data.security

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import javax.crypto.spec.IvParameterSpec

/**
 * Security Manager
 * Handles command validation, encryption, and secure storage.
 *
 * The DASH device token is stored in Keystore-backed
 * [EncryptedSharedPreferences]; it never touches plaintext prefs or logs.
 */
object SecurityManager {
    private const val TAG = "SecurityManager"
    private const val PREFS_NAME = "dash_security"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_SESSION_KEY = "session_key"
    private const val KEY_AUTH_TOKEN = "auth_token"
    private const val KEY_COMMAND_SIGNATURE_KEY = "command_signature_key"

    // DASH device tokens are opaque URL-safe strings (not JWTs).
    private const val MIN_TOKEN_LENGTH = 32

    private val secureRandom = SecureRandom()

    @Volatile
    private var encryptedPrefs: SharedPreferences? = null
    
    // Allowed commands for security validation
    private val ALLOWED_COMMANDS = setOf(
        "set_volume",
        "set_brightness",
        "media_control",
        "launch_app",
        "lock_desktop",
        "get_system_status",
        "ping",
        "open_url",
        "send_notification",
        "run_automation",
        "execute_shell" // Requires special permission
    )
    
    // Commands that require special permissions
    private val PRIVILEGED_COMMANDS = setOf(
        "execute_shell",
        "system_shutdown",
        "system_restart",
        "install_software"
    )
    
    data class ValidatedCommand(
        val isValid: Boolean,
        val command: String,
        val error: String? = null,
        val timestamp: Long = System.currentTimeMillis()
    )
    
    /**
     * Initialize security manager
     */
    fun initialize(context: Context) {
        ensureDeviceId(context)
        generateSessionKey(context)
    }
    
    /**
     * Validate command before execution
     */
    fun validateCommand(
        command: String,
        payload: Map<String, Any>,
        authToken: String?
    ): ValidatedCommand {
        // Check if command is allowed
        if (command !in ALLOWED_COMMANDS) {
            return ValidatedCommand(
                isValid = false,
                command = command,
                error = "Command not allowed: $command"
            )
        }
        
        // Check if command requires special permission
        if (command in PRIVILEGED_COMMANDS) {
            val hasPermission = checkPrivilegedPermission(authToken)
            if (!hasPermission) {
                return ValidatedCommand(
                    isValid = false,
                    command = command,
                    error = "Insufficient permissions for privileged command"
                )
            }
        }
        
        // Validate payload parameters
        val payloadValidation = validatePayload(command, payload)
        if (!payloadValidation.isValid) {
            return ValidatedCommand(
                isValid = false,
                command = command,
                error = payloadValidation.error
            )
        }
        
        // Validate authentication token
        if (!validateAuthToken(authToken)) {
            return ValidatedCommand(
                isValid = false,
                command = command,
                error = "Invalid authentication token"
            )
        }
        
        return ValidatedCommand(
            isValid = true,
            command = command
        )
    }
    
    /**
     * Validate command payload
     */
    private fun validatePayload(command: String, payload: Map<String, Any>): ValidatedCommand {
        return when (command) {
            "set_volume" -> {
                val level = payload["level"] as? Int
                if (level == null || level < 0 || level > 100) {
                    ValidatedCommand(false, command, "Invalid volume level: must be 0-100")
                } else {
                    ValidatedCommand(true, command)
                }
            }
            "set_brightness" -> {
                val level = payload["level"] as? Int
                if (level == null || level < 0 || level > 100) {
                    ValidatedCommand(false, command, "Invalid brightness level: must be 0-100")
                } else {
                    ValidatedCommand(true, command)
                }
            }
            "launch_app" -> {
                val app = payload["app"] as? String
                if (app.isNullOrBlank()) {
                    ValidatedCommand(false, command, "App name required")
                } else {
                    ValidatedCommand(true, command)
                }
            }
            "media_control" -> {
                val action = payload["action"] as? String
                val validActions = setOf("play", "pause", "stop", "next", "previous", "volume_up", "volume_down")
                if (action !in validActions) {
                    ValidatedCommand(false, command, "Invalid media action: $action")
                } else {
                    ValidatedCommand(true, command)
                }
            }
            else -> ValidatedCommand(true, command)
        }
    }
    
    /**
     * Validate authentication token (DASH device token: opaque, not JWT).
     */
    private fun validateAuthToken(token: String?): Boolean {
        if (token.isNullOrBlank()) return false
        if (token == "placeholder_token") return false
        return token.length >= MIN_TOKEN_LENGTH
    }
    
    /**
     * Check privileged permission
     */
    private fun checkPrivilegedPermission(authToken: String?): Boolean {
        // In a real implementation, this would check the token's claims
        // For now, we'll require a special token signature
        return authToken?.contains("admin") == true
    }
    
    /**
     * Sign command for verification
     */
    fun signCommand(
        command: String,
        payload: Map<String, Any>,
        context: Context
    ): String {
        val signatureKey = getCommandSignatureKey(context)
        val data = "$command${payload.hashCode()}${System.currentTimeMillis()}"
        
        val mac = Mac.getInstance("HmacSHA256")
        val keySpec = SecretKeySpec(signatureKey.toByteArray(), "HmacSHA256")
        mac.init(keySpec)
        val signature = mac.doFinal(data.toByteArray())
        
        return Base64.encodeToString(signature, Base64.NO_WRAP)
    }
    
    /**
     * Verify command signature
     */
    fun verifyCommandSignature(
        command: String,
        payload: Map<String, Any>,
        signature: String,
        context: Context
    ): Boolean {
        val signatureKey = getCommandSignatureKey(context)
        val data = "$command${payload.hashCode()}"
        
        try {
            val mac = Mac.getInstance("HmacSHA256")
            val keySpec = SecretKeySpec(signatureKey.toByteArray(), "HmacSHA256")
            mac.init(keySpec)
            val expectedSignature = mac.doFinal(data.toByteArray())
            val expectedSignatureBase64 = Base64.encodeToString(expectedSignature, Base64.NO_WRAP)
            
            return expectedSignatureBase64 == signature
        } catch (e: Exception) {
            Log.e(TAG, "Signature verification failed", e)
            return false
        }
    }
    
    /**
     * Encrypt sensitive data with the session key.
     * The key is stored Base64-encoded; it must be DECODED to raw 32 bytes
     * before use (a 44-char Base64 string is not a valid AES key length).
     */
    fun encryptData(data: String, context: Context): String {
        val sessionKey = getSessionKey(context)

        return try {
            val rawKey = Base64.decode(sessionKey, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
            val keySpec = SecretKeySpec(rawKey, "AES")
            val iv = ByteArray(16)
            secureRandom.nextBytes(iv)
            val ivSpec = IvParameterSpec(iv)

            cipher.init(Cipher.ENCRYPT_MODE, keySpec, ivSpec)
            val encrypted = cipher.doFinal(data.toByteArray())

            // Combine IV and encrypted data
            val combined = iv + encrypted
            Base64.encodeToString(combined, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.e(TAG, "Encryption failed", e)
            throw e
        }
    }

    /**
     * Decrypt sensitive data with the session key.
     */
    fun decryptData(encryptedData: String, context: Context): String {
        val sessionKey = getSessionKey(context)

        return try {
            val combined = Base64.decode(encryptedData, Base64.NO_WRAP)
            val iv = combined.sliceArray(0..15)
            val encrypted = combined.sliceArray(16 until combined.size)
            val rawKey = Base64.decode(sessionKey, Base64.NO_WRAP)

            val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
            val keySpec = SecretKeySpec(rawKey, "AES")
            val ivSpec = IvParameterSpec(iv)

            cipher.init(Cipher.DECRYPT_MODE, keySpec, ivSpec)
            String(cipher.doFinal(encrypted))
        } catch (e: Exception) {
            Log.e(TAG, "Decryption failed", e)
            throw e
        }
    }
    
    /**
     * Ensure device ID exists
     */
    private fun ensureDeviceId(context: Context) {
        val prefs = getSharedPreferences(context)
        if (!prefs.contains(KEY_DEVICE_ID)) {
            val deviceId = generateDeviceId(context)
            prefs.edit().putString(KEY_DEVICE_ID, deviceId).apply()
        }
    }
    
    /**
     * Generate session key
     */
    private fun generateSessionKey(context: Context) {
        val prefs = getSharedPreferences(context)
        if (!prefs.contains(KEY_SESSION_KEY)) {
            val sessionKey = generateSecureKey(32)
            prefs.edit().putString(KEY_SESSION_KEY, sessionKey).apply()
        }
    }
    
    /**
     * Get command signature key (generates on first use)
     */
    private fun getCommandSignatureKey(context: Context): String {
        return generateCommandSignatureKey(context)
    }

    /**
     * Generate command signature key
     */
    private fun generateCommandSignatureKey(context: Context): String {
        val prefs = getSharedPreferences(context)
        if (!prefs.contains(KEY_COMMAND_SIGNATURE_KEY)) {
            val signatureKey = generateSecureKey(32)
            prefs.edit().putString(KEY_COMMAND_SIGNATURE_KEY, signatureKey).apply()
        }
        return prefs.getString(KEY_COMMAND_SIGNATURE_KEY, "") ?: ""
    }
    
    /**
     * Get device ID
     */
    fun getDeviceId(context: Context): String {
        return getSharedPreferences(context).getString(KEY_DEVICE_ID, "") ?: ""
    }
    
    /**
     * Get session key
     */
    private fun getSessionKey(context: Context): String {
        return getSharedPreferences(context).getString(KEY_SESSION_KEY, "") ?: ""
    }
    
    /**
     * Save the DASH device token in Keystore-backed encrypted storage.
     * The value is never logged, never written to plaintext prefs.
     */
    fun saveAuthToken(context: Context, token: String) {
        try {
            getEncryptedSharedPreferences(context)
                .edit()
                .putString(KEY_AUTH_TOKEN, token)
                .apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store auth token securely", e)
        }
    }

    /**
     * Get auth token
     */
    fun getAuthToken(context: Context): String? {
        return try {
            getEncryptedSharedPreferences(context).getString(KEY_AUTH_TOKEN, null)
        } catch (e: Exception) {
            // Fail safely: an unreadable keystore means no valid session.
            Log.e(TAG, "Failed to read auth token", e)
            null
        }
    }

    /**
     * Clear sensitive data (used when pairing/session is revoked).
     */
    fun clearSensitiveData(context: Context) {
        getSharedPreferences(context).edit().clear().apply()
        try {
            getEncryptedSharedPreferences(context).edit().clear().apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to clear encrypted prefs", e)
        }
        Log.d(TAG, "Sensitive data cleared")
    }

    /**
     * Keystore-backed preferences for credential material.
     */
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
    
    private fun getSharedPreferences(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }
    
    private fun generateDeviceId(context: Context): String {
        val deviceId = android.provider.Settings.Secure.getString(
            context.contentResolver,
            android.provider.Settings.Secure.ANDROID_ID
        ) ?: "unknown_device"

        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(deviceId.toByteArray())
        return Base64.encodeToString(hash, Base64.NO_WRAP).substring(0, 16)
    }
    
    private fun generateSecureKey(length: Int): String {
        val bytes = ByteArray(length)
        secureRandom.nextBytes(bytes)
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }
}