package com.aistudio.dashcompanion.data.pairing

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import android.util.Log
import com.aistudio.dashcompanion.data.discovery.DesktopDiscoveryManager
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.collect
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.spec.PKCS8EncodedKeySpec
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Desktop Pairing Manager
 * Handles secure pairing flow between Android and DASH Desktop
 * Uses ECDH key exchange for secure communication
 */
object DesktopPairingManager {
    private const val TAG = "DesktopPairing"
    private const val PREFS_NAME = "dash_pairing"
    private const val KEY_DESKTOP_ID = "desktop_id"
    private const val KEY_DESKTOP_NAME = "desktop_name"
    private const val KEY_DESKTOP_HOST = "desktop_host"
    private const val KEY_DESKTOP_PORT = "desktop_port"
    private const val KEY_DESKTOP_IP = "desktop_ip"
    private const val KEY_AUTH_TOKEN = "auth_token"
    private const val KEY_PAIRING_TIME = "pairing_time"
    private const val KEY_DEVICE_FINGERPRINT = "device_fingerprint"
    
    enum class PairingState {
        None,
        Discovering,
        Discovered,
        PairingRequested,
        PairingConfirmed,
        Paired,
        Failed
    }
    
    data class PairedDesktop(
        val id: String,
        val name: String,
        val host: String,
        val port: Int,
        val ip: String,
        val authToken: String,
        val pairingTime: Long,
        val deviceFingerprint: String
    )
    
    data class PairingRequest(
        val deviceId: String,
        val deviceName: String,
        val publicKey: String,
        val timestamp: Long,
        val deviceFingerprint: String
    )
    
    data class PairingResponse(
        val desktopId: String,
        val desktopName: String,
        val publicKey: String,
        val authToken: String,
        val timestamp: Long,
        val approved: Boolean
    )
    
    private val _pairingState = MutableStateFlow<PairingState>(PairingState.None)
    val pairingState: Flow<PairingState> = _pairingState.asStateFlow()
    
    private val _discoveredDesktops = MutableStateFlow<List<DesktopDiscoveryManager.DiscoveredDesktop>>(emptyList())
    val discoveredDesktops: Flow<List<DesktopDiscoveryManager.DiscoveredDesktop>> = _discoveredDesktops.asStateFlow()
    
    private var secureRandom = SecureRandom()
    
    /**
     * Discover available DASH Desktop instances
     */
    fun discoverDesktops(context: Context): Flow<DesktopDiscoveryManager.DiscoveredDesktop> {
        _pairingState.value = PairingState.Discovering
        return flow {
            DesktopDiscoveryManager.discoverDesktops(context).collect { desktop ->
                _discoveredDesktops.value = _discoveredDesktops.value + desktop
                emit(desktop)
            }
            _pairingState.value = PairingState.Discovered
        }
    }
    
    /**
     * Initiate pairing with a discovered desktop
     */
    suspend fun initiatePairing(
        context: Context,
        desktop: DesktopDiscoveryManager.DiscoveredDesktop,
        deviceName: String = "Android Device"
    ): PairingRequest {
        _pairingState.value = PairingState.PairingRequested
        
        try {
            // Generate ECDH key pair for this pairing session
            val keyPair = generateKeyPair()
            val publicKeyString = Base64.encodeToString(keyPair.public.encoded, Base64.NO_WRAP)
            
            // Generate device fingerprint
            val deviceFingerprint = generateDeviceFingerprint(context)
            
            val request = PairingRequest(
                deviceId = getDeviceId(context),
                deviceName = deviceName,
                publicKey = publicKeyString,
                timestamp = System.currentTimeMillis(),
                deviceFingerprint = deviceFingerprint
            )
            
            // In a real implementation, this would be sent to the desktop via HTTP/HTTPS
            // For now, we'll simulate the pairing response
            Log.d(TAG, "Pairing request created for ${desktop.name}")
            
            return request
        } catch (e: Exception) {
            Log.e(TAG, "Pairing request failed", e)
            _pairingState.value = PairingState.Failed
            throw e
        }
    }
    
    /**
     * Confirm pairing and store credentials
     */
    suspend fun confirmPairing(
        context: Context,
        desktop: DesktopDiscoveryManager.DiscoveredDesktop,
        response: PairingResponse
    ): PairedDesktop {
        try {
            if (!response.approved) {
                _pairingState.value = PairingState.Failed
                throw Exception("Pairing rejected by desktop")
            }
            
            // Validate response timestamp (prevent replay attacks)
            val currentTime = System.currentTimeMillis()
            if (currentTime - response.timestamp > 60000) { // 1 minute window
                throw Exception("Pairing response expired")
            }
            
            // Store pairing information securely
            val pairedDesktop = PairedDesktop(
                id = response.desktopId,
                name = response.desktopName,
                host = desktop.host,
                port = desktop.port,
                ip = desktop.ip,
                authToken = response.authToken,
                pairingTime = currentTime,
                deviceFingerprint = generateDeviceFingerprint(context)
            )
            
            savePairedDesktop(context, pairedDesktop)
            _pairingState.value = PairingState.Paired
            
            Log.d(TAG, "Successfully paired with ${response.desktopName}")
            return pairedDesktop
        } catch (e: Exception) {
            Log.e(TAG, "Pairing confirmation failed", e)
            _pairingState.value = PairingState.Failed
            throw e
        }
    }
    
    /**
     * Get currently paired desktop
     */
    fun getPairedDesktop(context: Context): PairedDesktop? {
        val prefs = getSharedPreferences(context)
        val id = prefs.getString(KEY_DESKTOP_ID, null) ?: return null
        val name = prefs.getString(KEY_DESKTOP_NAME, null) ?: return null
        val host = prefs.getString(KEY_DESKTOP_HOST, null) ?: return null
        val port = prefs.getInt(KEY_DESKTOP_PORT, -1).takeIf { it != -1 } ?: return null
        val ip = prefs.getString(KEY_DESKTOP_IP, null) ?: return null
        val authToken = prefs.getString(KEY_AUTH_TOKEN, null) ?: return null
        val pairingTime = prefs.getLong(KEY_PAIRING_TIME, 0).takeIf { it != 0L } ?: return null
        val deviceFingerprint = prefs.getString(KEY_DEVICE_FINGERPRINT, null) ?: return null
        
        return PairedDesktop(
            id = id,
            name = name,
            host = host,
            port = port,
            ip = ip,
            authToken = authToken,
            pairingTime = pairingTime,
            deviceFingerprint = deviceFingerprint
        )
    }
    
    /**
     * Forget paired desktop
     */
    fun forgetDesktop(context: Context) {
        getSharedPreferences(context).edit().clear().apply()
        _pairingState.value = PairingState.None
        Log.d(TAG, "Desktop pairing forgotten")
    }
    
    /**
     * Check if device is paired
     */
    fun isPaired(context: Context): Boolean {
        return getPairedDesktop(context) != null
    }
    
    private fun savePairedDesktop(context: Context, desktop: PairedDesktop) {
        getSharedPreferences(context).edit().apply {
            putString(KEY_DESKTOP_ID, desktop.id)
            putString(KEY_DESKTOP_NAME, desktop.name)
            putString(KEY_DESKTOP_HOST, desktop.host)
            putInt(KEY_DESKTOP_PORT, desktop.port)
            putString(KEY_DESKTOP_IP, desktop.ip)
            putString(KEY_AUTH_TOKEN, desktop.authToken)
            putLong(KEY_PAIRING_TIME, desktop.pairingTime)
            putString(KEY_DEVICE_FINGERPRINT, desktop.deviceFingerprint)
        }.apply()
    }
    
    private fun getSharedPreferences(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }
    
    private fun generateKeyPair(): java.security.KeyPair {
        val keyGen = KeyPairGenerator.getInstance("EC")
        keyGen.initialize(256)
        return keyGen.generateKeyPair()
    }
    
    private fun generateDeviceFingerprint(context: Context): String {
        val deviceId = getDeviceId(context)
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(deviceId.toByteArray())
        return Base64.encodeToString(hash, Base64.NO_WRAP).substring(0, 16)
    }
    
    private fun getDeviceId(context: Context): String {
        return android.provider.Settings.Secure.getString(
            context.contentResolver,
            android.provider.Settings.Secure.ANDROID_ID
        ) ?: "unknown_device"
    }
}