package com.aistudio.dashcompanion.data.model

import com.squareup.moshi.Json

data class SystemState(
    @Json(name = "cpu") val cpu: CpuInfo = CpuInfo(),
    @Json(name = "ram") val ram: RamInfo = RamInfo(),
    @Json(name = "gpu") val gpu: GpuInfo = GpuInfo(),
    @Json(name = "disk") val disk: DiskInfo = DiskInfo(),
    @Json(name = "network") val network: NetworkInfo = NetworkInfo(),
    @Json(name = "battery") val battery: BatteryInfo = BatteryInfo(),
    @Json(name = "system") val system: SystemInfo = SystemInfo(),
    @Json(name = "processes") val processes: List<ProcessInfo> = emptyList(),
    @Json(name = "applications") val applications: List<ApplicationInfo> = emptyList(),
    @Json(name = "timestamp") val timestamp: Double = 0.0
)

data class CpuInfo(
    @Json(name = "percent") val percent: Double = 0.0,
    @Json(name = "frequency") val frequency: Double = 0.0,
    @Json(name = "cores") val cores: Int = 0,
    @Json(name = "temperature") val temperature: Double = 0.0,
    @Json(name = "load_avg") val loadAvg: List<Double> = emptyList()
)

data class RamInfo(
    @Json(name = "total") val total: Double = 0.0,
    @Json(name = "used") val used: Double = 0.0,
    @Json(name = "free") val free: Double = 0.0,
    @Json(name = "percent") val percent: Double = 0.0
)

data class GpuInfo(
    @Json(name = "name") val name: String = "",
    @Json(name = "memory_used") val memoryUsed: Double = 0.0,
    @Json(name = "memory_total") val memoryTotal: Double = 0.0,
    @Json(name = "percent") val percent: Double = 0.0,
    @Json(name = "temperature") val temperature: Double = 0.0,
    @Json(name = "utilization") val utilization: Double = 0.0
)

data class DiskInfo(
    @Json(name = "total") val total: Double = 0.0,
    @Json(name = "used") val used: Double = 0.0,
    @Json(name = "free") val free: Double = 0.0,
    @Json(name = "percent") val percent: Double = 0.0,
    @Json(name = "read_speed") val readSpeed: Double = 0.0,
    @Json(name = "write_speed") val writeSpeed: Double = 0.0
)

data class NetworkInfo(
    @Json(name = "download_speed") val downloadSpeed: Double = 0.0,
    @Json(name = "upload_speed") val uploadSpeed: Double = 0.0,
    @Json(name = "bytes_sent") val bytesSent: Double = 0.0,
    @Json(name = "bytes_recv") val bytesRecv: Double = 0.0,
    @Json(name = "connections") val connections: Int = 0,
    @Json(name = "wifi_enabled") val wifiEnabled: Boolean = false,
    @Json(name = "bluetooth_enabled") val bluetoothEnabled: Boolean = false
)

data class BatteryInfo(
    @Json(name = "percent") val percent: Double = 0.0,
    @Json(name = "charging") val charging: Boolean = false,
    @Json(name = "time_remaining") val timeRemaining: Int = 0,
    @Json(name = "health") val health: String = "Good"
)

data class SystemInfo(
    @Json(name = "hostname") val hostname: String = "",
    @Json(name = "platform") val platform: String = "",
    @Json(name = "uptime") val uptime: Long = 0,
    @Json(name = "temperature") val temperature: Double = 0.0
)

data class ProcessInfo(
    @Json(name = "pid") val pid: Int = 0,
    @Json(name = "name") val name: String = "",
    @Json(name = "cpu_percent") val cpuPercent: Double = 0.0,
    @Json(name = "memory_percent") val memoryPercent: Double = 0.0,
    @Json(name = "status") val status: String = ""
)

data class ApplicationInfo(
    @Json(name = "name") val name: String = "",
    @Json(name = "window_title") val windowTitle: String = "",
    @Json(name = "pid") val pid: Int = 0,
    @Json(name = "focused") val focused: Boolean = false
)
