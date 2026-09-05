package com.aistudio.dashcompanion.data.discovery

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Desktop Discovery Manager
 * Handles automatic discovery of DASH Desktop instances on the local network
 * Uses mDNS/Bonjour for reliable discovery with UDP broadcast fallback
 */
object DesktopDiscoveryManager {
    private const val TAG = "DesktopDiscovery"
    private const val SERVICE_TYPE = "_dash._tcp."
    private const val SERVICE_NAME = "DASH Desktop"
    private const val DISCOVERY_TIMEOUT_MS = 5000L
    private const val UDP_BROADCAST_PORT = 8765
    private const val UDP_DISCOVERY_MESSAGE = "DASH_DISCOVERY_REQUEST"
    private const val UDP_RESPONSE_MESSAGE = "DASH_DISCOVERY_RESPONSE"
    
    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var resolveListener: NsdManager.ResolveListener? = null

    /** Scope used to run suspend resolution from NSD listener callbacks. */
    private val discoveryScope = CoroutineScope(Dispatchers.IO + Job())
    
    data class DiscoveredDesktop(
        val name: String,
        val host: String,
        val port: Int,
        val ip: String,
        val version: String = "unknown",
        val id: String = ""
    )
    
    /**
     * Discover DASH Desktop instances using mDNS
     */
    fun discoverDesktops(context: Context): Flow<DiscoveredDesktop> = flow {
        try {
            val discoveredDesktops = mutableSetOf<DiscoveredDesktop>()
            val discoveryChannel = Channel<DiscoveredDesktop>()
            
            val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
            
            discoveryListener = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(regType: String) {
                    Log.d(TAG, "Discovery started: $regType")
                }
                
                override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                    Log.d(TAG, "Service found: ${serviceInfo.serviceName}")
                    if (serviceInfo.serviceName.contains("DASH", ignoreCase = true)) {
                        // Resolve the service to get IP and port (suspend — run in scope)
                        discoveryScope.launch {
                            resolveService(nsd, serviceInfo, discoveryChannel)
                        }
                    }
                }
                
                override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                    Log.d(TAG, "Service lost: ${serviceInfo.serviceName}")
                }
                
                override fun onDiscoveryStopped(serviceType: String) {
                    Log.d(TAG, "Discovery stopped: $serviceType")
                }
                
                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.e(TAG, "Discovery failed: $serviceType, error: $errorCode")
                }
                
                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.e(TAG, "Stop discovery failed: $serviceType, error: $errorCode")
                }
            }
            
            nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
            
            // Collect discovered desktops for timeout period
            var endTime = System.currentTimeMillis() + DISCOVERY_TIMEOUT_MS
            while (System.currentTimeMillis() < endTime) {
                val desktop = discoveryChannel.tryReceive().getOrNull()
                if (desktop != null && !discoveredDesktops.contains(desktop)) {
                    discoveredDesktops.add(desktop)
                    emit(desktop)
                }
                kotlinx.coroutines.delay(100)
            }
            
            // Stop discovery
            nsd.stopServiceDiscovery(discoveryListener)
            
        } catch (e: Exception) {
            Log.e(TAG, "Discovery error", e)
            // Fallback to UDP broadcast discovery
            discoverViaUDPBroadcast().collect { emit(it) }
        }
    }
    
    /**
     * Fallback UDP broadcast discovery
     */
    private suspend fun discoverViaUDPBroadcast(): Flow<DiscoveredDesktop> = flow {
        try {
            val socket = DatagramSocket()
            socket.broadcast = true
            socket.soTimeout = DISCOVERY_TIMEOUT_MS.toInt()
            
            val message = UDP_DISCOVERY_MESSAGE.toByteArray()
            val packet = DatagramPacket(
                message,
                message.size,
                InetAddress.getByName("255.255.255.255"),
                UDP_BROADCAST_PORT
            )
            
            Log.d(TAG, "Sending UDP broadcast discovery")
            socket.send(packet)
            
            // Listen for responses
            val buffer = ByteArray(1024)
            while (true) {
                val responsePacket = DatagramPacket(buffer, buffer.size)
                socket.receive(responsePacket)
                
                val response = String(responsePacket.data, 0, responsePacket.length)
                if (response.startsWith(UDP_RESPONSE_MESSAGE)) {
                    val parts = response.split("|")
                    if (parts.size >= 3) {
                        val desktop = DiscoveredDesktop(
                            name = parts[1],
                            host = responsePacket.address.hostAddress ?: "",
                            port = parts[2].toIntOrNull() ?: 8765,
                            ip = responsePacket.address.hostAddress ?: "",
                            version = if (parts.size > 3) parts[3] else "unknown",
                            id = if (parts.size > 4) parts[4] else ""
                        )
                        emit(desktop)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "UDP discovery error", e)
        }
    }
    
    /**
     * Resolve mDNS service to get actual IP and port
     */
    private suspend fun resolveService(
        nsd: NsdManager,
        serviceInfo: NsdServiceInfo,
        channel: Channel<DiscoveredDesktop>
    ) {
        try {
            suspendCancellableCoroutine<Unit> { continuation ->
                resolveListener = object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                        Log.e(TAG, "Resolve failed: ${serviceInfo.serviceName}, error: $errorCode")
                        continuation.resumeWithException(Exception("Resolve failed: $errorCode"))
                    }
                    
                    override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                        Log.d(TAG, "Service resolved: ${serviceInfo.serviceName}")
                        val desktop = DiscoveredDesktop(
                            name = serviceInfo.serviceName,
                            host = serviceInfo.host.hostName ?: "",
                            port = serviceInfo.port,
                            ip = serviceInfo.host.hostAddress ?: "",
                            version = serviceInfo.attributes["version"]?.toString(Charsets.UTF_8) ?: "unknown",
                            id = serviceInfo.attributes["id"]?.toString(Charsets.UTF_8) ?: ""
                        )
                        channel.trySend(desktop)
                        continuation.resume(Unit)
                    }
                }
                nsd.resolveService(serviceInfo, resolveListener)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Resolve service error", e)
        }
    }
    
    /**
     * Stop any ongoing discovery
     */
    fun stopDiscovery() {
        try {
            nsdManager?.stopServiceDiscovery(discoveryListener)
            discoveryListener = null
            resolveListener = null
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping discovery", e)
        }
    }
}