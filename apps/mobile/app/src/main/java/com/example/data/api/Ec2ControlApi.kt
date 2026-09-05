package com.example.data.api

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.example.data.config.AppConfig
import java.util.concurrent.TimeUnit

/**
 * EC2 Control — start/stop the cloud backend from the Android app.
 * Talks to the LOCAL backend (which has AWS CLI access).
 */
object Ec2ControlApi {
    private var api: Ec2Service? = null

    fun get(): Ec2Service {
        if (api == null) {
            val client = OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build()
            val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
            api = Retrofit.Builder()
                .baseUrl(AppConfig.REST_BASE_URL)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(Ec2Service::class.java)
        }
        return api!!
    }
}

interface Ec2Service {
    @GET("ec2/status")
    suspend fun getStatus(): Ec2StatusResponse

    @POST("ec2/start")
    suspend fun startInstance(): Ec2ActionResponse

    @POST("ec2/stop")
    suspend fun stopInstance(): Ec2ActionResponse

    @GET("ec2/cloud-status")
    suspend fun getCloudStatus(): CloudStatusResponse
}

data class Ec2StatusResponse(
    val instance_id: String = "",
    val state: String = "unknown",
    val public_ip: String = "",
    val instance_type: String = "",
    val cloud_backend_url: String = "",
    val error: String? = null
)

data class Ec2ActionResponse(
    val ok: Boolean = false,
    val message: String = "",
    val error: String? = null,
    val instance_id: String? = null,
    val public_ip: String? = null
)

data class CloudStatusResponse(
    val reachable: Boolean = false,
    val health: Map<String, Any>? = null,
    val error: String? = null
)
