package com.example.data.api

import android.util.Log
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.util.concurrent.TimeUnit

/**
 * CloudRelayApi — talks to the DASH backend cloud relay.
 *
 * Smart fallback: tries local backend first, then Fly.io cloud.
 * When the PC is on, local works. When PC is off, cloud relay
 * (Supabase-backed) tells Android the PC status and can trigger WoL.
 */
object CloudRelayApi {
    private const val TAG = "CloudRelayApi"
    private var localApi: CloudRelayService? = null
    private var cloudApi: CloudRelayService? = null

    // Fly.io cloud backend URL
    private const val CLOUD_BASE_URL = "http://15.206.185.189:8001/api/v1/"

    /** Get the cloud-only relay service (Fly.io). */
    fun get(): CloudRelayService {
        if (cloudApi == null) {
            val client = OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .build()

            val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
            cloudApi = Retrofit.Builder()
                .baseUrl(CLOUD_BASE_URL)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(CloudRelayService::class.java)
        }
        return cloudApi!!
    }

    /** Get the local relay service (same as main backend). */
    fun getLocal(baseUrl: String): CloudRelayService {
        val normalizedUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        if (localApi == null || _localBaseUrl != normalizedUrl) {
            val client = OkHttpClient.Builder()
                .connectTimeout(3, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.SECONDS)
                .build()

            val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
            localApi = Retrofit.Builder()
                .baseUrl(normalizedUrl)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(CloudRelayService::class.java)
            _localBaseUrl = normalizedUrl
        }
        return localApi!!
    }

    private var _localBaseUrl: String = ""

    /**
     * Smart status check: tries local backend first, then cloud.
     * Returns Pair(status, isCloud) where isCloud tells caller which source responded.
     */
    suspend fun smartGetPcStatus(localBaseUrl: String): Pair<PcStatusResponse?, Boolean> {
        // 1. Try local backend first (fast, reliable when PC is on)
        try {
            val local = getLocal(localBaseUrl)
            val status = local.getPcStatus()
            if (status.status != "error") {
                Log.d(TAG, "PC status via local: ${status.status}")
                return Pair(status, false)
            }
        } catch (e: Exception) {
            Log.d(TAG, "Local relay unreachable: ${e.message}")
        }

        // 2. Fall back to cloud relay (Fly.io + Supabase)
        try {
            val status = get().getPcStatus()
            Log.d(TAG, "PC status via cloud: ${status.status}")
            return Pair(status, true)
        } catch (e: Exception) {
            Log.w(TAG, "Cloud relay unreachable: ${e.message}")
        }

        return Pair(null, false)
    }

    /**
     * Smart registration: register with both local and cloud relay.
     */
    suspend fun smartRegister(request: RelayRegisterRequest, localBaseUrl: String?) {
        // Register with local relay
        if (!localBaseUrl.isNullOrBlank()) {
            try {
                getLocal(localBaseUrl).registerDevice(request)
                Log.i(TAG, "Registered with local relay")
            } catch (e: Exception) {
                Log.d(TAG, "Local registration failed: ${e.message}")
            }
        }

        // Register with cloud relay
        try {
            get().registerDevice(request)
            Log.i(TAG, "Registered with cloud relay")
        } catch (e: Exception) {
            Log.w(TAG, "Cloud registration failed: ${e.message}")
        }
    }

    /**
     * Smart WoL: try cloud relay first (works from anywhere), then local.
     */
    suspend fun smartWoL(request: RelayWoLRequest, localBaseUrl: String?): RelayWoLResponse? {
        // 1. Try cloud relay (works even when PC is off, from anywhere)
        try {
            val result = get().triggerWoL(request)
            if (result.ok) {
                Log.i(TAG, "WoL via cloud: ${result.note}")
                return result
            }
        } catch (e: Exception) {
            Log.d(TAG, "Cloud WoL failed: ${e.message}")
        }

        // 2. Try local relay
        if (!localBaseUrl.isNullOrBlank()) {
            try {
                val result = getLocal(localBaseUrl).triggerWoL(request)
                if (result.ok) {
                    Log.i(TAG, "WoL via local: ${result.note}")
                    return result
                }
            } catch (e: Exception) {
                Log.d(TAG, "Local WoL failed: ${e.message}")
            }
        }

        return null
    }
}

interface CloudRelayService {
    @GET("relay/pc-status")
    suspend fun getPcStatus(): PcStatusResponse

    @POST("relay/register")
    suspend fun registerDevice(@Body request: RelayRegisterRequest): RelayResponse

    @POST("relay/heartbeat")
    suspend fun heartbeat(@Body request: RelayHeartbeatRequest): RelayResponse

    @POST("relay/tunnel")
    suspend fun registerTunnel(@Body request: RelayTunnelRequest): RelayResponse

    @POST("relay/wol")
    suspend fun triggerWoL(@Body request: RelayWoLRequest): RelayWoLResponse

    @GET("relay/device/{deviceId}")
    suspend fun getDevice(@Path("deviceId") deviceId: String): PcStatusResponse

    @GET("relay/devices")
    suspend fun listDevices(
        @Query("platform") platform: String? = null,
        @Query("online_only") onlineOnly: Boolean = false
    ): DevicesResponse
}

// ── Request/Response Models ─────────────────────────────────

data class PcStatusResponse(
    val status: String = "unknown",
    val device_id: String = "",
    val name: String = "",
    val tunnel_url: String = "",
    val local_ip: String = "",
    val mac_address: String = "",
    val is_stale: Boolean = false,
    val last_seen_at: String? = null,
    val capabilities: List<String> = emptyList()
)

data class RelayRegisterRequest(
    val device_id: String,
    val name: String = "DASH Android",
    val platform: String = "android",
    val local_ip: String = "",
    val mac_address: String = "",
    val tunnel_url: String = "",
    val capabilities: List<String> = emptyList()
)

data class RelayHeartbeatRequest(
    val device_id: String,
    val state: Map<String, Any> = emptyMap()
)

data class RelayTunnelRequest(
    val device_id: String,
    val tunnel_url: String,
    val service: String = "ollama"
)

data class RelayWoLRequest(
    val device_id: String,
    val mac_address: String? = null
)

data class RelayWoLResponse(
    val ok: Boolean = false,
    val mac_address: String = "",
    val wol_result: Map<String, Any>? = null,
    val note: String = ""
)

data class RelayResponse(
    val ok: Boolean = false,
    val error: String? = null
)

data class DevicesResponse(
    val devices: List<PcStatusResponse> = emptyList(),
    val count: Int = 0
)
