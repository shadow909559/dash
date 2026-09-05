package com.example.data.model

data class SystemMetrics(
    val pcName: String = "DESKTOP-NEURAL-01",
    val isPcOnline: Boolean = true,
    val cpuUsage: Int = 0,
    val ramUsage: Int = 0,
    val gpuUsage: Int = 0,
    val storageUsage: Int = 0,
    val latencyMs: Int = 0,
    val cpuTotalGb: Float = 0f,
    val ramTotalGb: Float = 0f,
    val gpuName: String = "",
    val gpuMemoryUsedMb: Float = 0f,
    val gpuMemoryTotalMb: Float = 0f,
    val activeAgentsCount: Int = 2,
    val pendingApprovalsCount: Int = 2,
    val activeTasksCount: Int = 4,
    val awsRegion: String = "US-East-1 (N. Virginia)",
    val cloudStorageAllocatedTb: Float = 3.2f,
    val cloudStorageTotalLimitTb: Float = 5.0f,
    val isVaultSynced: Boolean = true,
    val lastSyncTime: String = "4m ago"
)

data class AiProviderOption(
    val id: String,
    val name: String,
    val type: String, // "LOCAL", "CLOUD", "CUSTOM"
    val modelName: String,
    val isConnected: Boolean,
    val latency: String,
    val description: String
)
