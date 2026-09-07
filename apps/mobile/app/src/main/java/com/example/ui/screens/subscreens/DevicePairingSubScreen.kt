package com.example.ui.screens.subscreens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.sp
import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import com.example.ui.components.GlassCard
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

/**
 * Device Pairing / Connection Settings screen.
 * Allows the user to configure the DASH backend connection and test it.
 */
@Composable
fun DevicePairingSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val connectionState by viewModel.connectionState.collectAsState()
    val systemMetrics by viewModel.systemMetrics.collectAsState()
    val scope = rememberCoroutineScope()

    var serverIp by remember { mutableStateOf(AppConfig.SERVER_IP) }
    var serverPort by remember { mutableStateOf(AppConfig.SERVER_PORT) }
    var deviceToken by remember { mutableStateOf(AppConfig.accessToken ?: "") }
    var isTesting by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var isTestSuccess by remember { mutableStateOf(false) }
    var pairingCode by remember { mutableStateOf("") }
    var isPairing by remember { mutableStateOf(false) }
    val context = LocalContext.current

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("device_pairing_screen")
    ) {
        SubScreenHeader(
            title = "Connection Settings",
            subtitle = "Configure DASH backend connection",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Connection Status Card
            item {
                val isConnected = connectionState == WebSocketManager.ConnectionState.Authenticated
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "CONNECTION STATUS",
                                style = MaterialTheme.typography.labelSmall,
                                color = dashColors().textMuted,
                                letterSpacing = 1.2.sp
                            )
                            Box(
                                modifier = Modifier
                                    .clip(CircleShape)
                                    .background(
                                        if (isConnected) DashSuccessGreen.copy(alpha = 0.12f)
                                        else DashErrorRed.copy(alpha = 0.12f)
                                    )
                                    .padding(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = when (connectionState) {
                                        WebSocketManager.ConnectionState.Authenticated -> "CONNECTED"
                                        WebSocketManager.ConnectionState.Connected -> "AUTHENTICATING"
                                        WebSocketManager.ConnectionState.AuthFailed -> "AUTH FAILED"
                                        WebSocketManager.ConnectionState.DisconnectedError -> "ERROR"
                                        else -> "DISCONNECTED"
                                    },
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (isConnected) DashSuccessGreen else DashErrorRed
                                )
                            }
                        }

                        // Backend info
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            InfoRow("Backend", "${AppConfig.SERVER_IP}:${AppConfig.SERVER_PORT}")
                            InfoRow("Host", systemMetrics.pcName)
                        }

                        // Connect / Disconnect buttons
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Button(
                                onClick = {
                                    AppConfig.setServer(serverIp, serverPort)
                                    com.example.data.security.SecurityManager.saveServerConfig(context, serverIp, serverPort)
                                    WebSocketManager.connect()
                                },
                                enabled = !isConnected,
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = DashCyanPrimary,
                                    disabledContainerColor = DashCyanPrimary.copy(alpha = 0.3f)
                                )
                            ) {
                                Text("Connect", color = dashColors().surface, fontWeight = FontWeight.Bold)
                            }
                            Button(
                                onClick = { WebSocketManager.disconnect() },
                                enabled = isConnected,
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = DashErrorRed.copy(alpha = 0.8f),
                                    disabledContainerColor = DashErrorRed.copy(alpha = 0.2f)
                                )
                            ) {
                                Text("Disconnect", color = dashColors().surface, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Server Configuration
            item {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "SERVER CONFIGURATION",
                            style = MaterialTheme.typography.labelSmall,
                            color = dashColors().textMuted,
                            letterSpacing = 1.2.sp
                        )

                        Text(
                            text = "Enter the IP address of your Windows PC.",
                            maxLines = 2,
                            style = MaterialTheme.typography.bodySmall,
                            color = dashColors().textSecondary
                        )

                        OutlinedTextField(
                            value = serverIp,
                            onValueChange = { serverIp = it },
                            label = { Text("Server IP", color = dashColors().textMuted) },
                            placeholder = { Text("192.168.1.x or 10.0.2.2", color = dashColors().textMuted) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashCyanPrimary,
                                unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow,
                                unfocusedContainerColor = dashColors().surfaceContainerLow,
                                focusedTextColor = dashColors().textPrimary,
                                unfocusedTextColor = dashColors().textPrimary
                            ),
                            singleLine = true
                        )

                        OutlinedTextField(
                            value = serverPort,
                            onValueChange = { serverPort = it },
                            label = { Text("Port", color = dashColors().textMuted) },
                            placeholder = { Text("8000", color = dashColors().textMuted) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashCyanPrimary,
                                unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow,
                                unfocusedContainerColor = dashColors().surfaceContainerLow,
                                focusedTextColor = dashColors().textPrimary,
                                unfocusedTextColor = dashColors().textPrimary
                            ),
                            singleLine = true
                        )

                        OutlinedTextField(
                            value = pairingCode,
                            onValueChange = { pairingCode = it },
                            label = { Text("Pairing Code", color = dashColors().textMuted) },
                            placeholder = { Text("Enter pairing code from DASH desktop", color = dashColors().textMuted) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashCyanPrimary,
                                unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow,
                                unfocusedContainerColor = dashColors().surfaceContainerLow,
                                focusedTextColor = dashColors().textPrimary,
                                unfocusedTextColor = dashColors().textPrimary
                            ),
                            singleLine = true
                        )

                        OutlinedTextField(
                            value = deviceToken,
                            onValueChange = { deviceToken = it },
                            label = { Text("Manual Device Token (optional)", color = dashColors().textMuted) },
                            placeholder = { Text("Paste from identity.json as fallback", color = dashColors().textMuted) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashPurpleSecondary,
                                unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow,
                                unfocusedContainerColor = dashColors().surfaceContainerLow,
                                focusedTextColor = dashColors().textPrimary,
                                unfocusedTextColor = dashColors().textPrimary
                            ),
                            singleLine = true
                        )
                        Text(
                            text = "Set DASH_PAIRING_CODE env var on PC, or paste device_token from identity.json",
                            style = MaterialTheme.typography.bodySmall,
                            color = dashColors().textMuted,
                            fontSize = 10.sp
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Button(
                                onClick = {
                                    isTesting = true
                                    testResult = null
                                    scope.launch {
                                        try {
                                            // Auto-pair if no manual token but pairing code is provided
                                            if (deviceToken.isBlank() && pairingCode.isNotBlank()) {
                                                isPairing = true
                                                val deviceId = com.example.data.security.SecurityManager.getDeviceId(context)
                                                val pairResult = com.example.data.api.DashApiService.devicePair(
                                                    deviceId, "DASH Android", pairingCode.trim()
                                                )
                                                val token = pairResult["device_token"] as? String
                                                if (!token.isNullOrBlank()) {
                                                    deviceToken = token
                                                    com.example.data.config.AppConfig.accessToken = token
                                                    com.example.data.security.SecurityManager.saveDeviceToken(context, token)
                                                    com.example.data.security.SecurityManager.saveAuthToken(context, token)
                                                    testResult = "Paired!"
                                                } else {
                                                    testResult = "Pairing failed"
                                                    isTestSuccess = false
                                                    isTesting = false
                                                    isPairing = false
                                                    return@launch
                                                }
                                                isPairing = false
                                            }
                                            if (deviceToken.isNotBlank()) {
                                                com.example.data.config.AppConfig.accessToken = deviceToken.trim()
                                                com.example.data.security.SecurityManager.saveAuthToken(context, deviceToken.trim())
                                                com.example.data.security.SecurityManager.saveDeviceToken(context, deviceToken.trim())
                                            }
                                            viewModel.updateServer(serverIp, serverPort)
                                            viewModel.testConnection(serverIp, serverPort)
                                            viewModel.connect()
                                            testResult = if (testResult == "Paired!") "Paired & connected!" else "Connection successful!"
                                            isTestSuccess = true
                                        } catch (e: Exception) {
                                            testResult = "Failed: ${e.message}"
                                            isTestSuccess = false
                                        } finally {
                                            isTesting = false
                                            isPairing = false
                                        }
                                    }
                                },
                                enabled = !isTesting,
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = DashSuccessGreen)
                            ) {
                                if (isTesting) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(16.dp),
                                        color = dashColors().surface,
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                }
                                Text(
                                    when {
                                        isPairing -> "Pairing..."
                                        isTesting -> "Testing..."
                                        else -> "Pair & Connect"
                                    },
                                    color = dashColors().surface,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Button(
                                onClick = {
                                    // Save device token
                                    if (deviceToken.isNotBlank()) {
                                        AppConfig.accessToken = deviceToken.trim()
                                        com.example.data.security.SecurityManager.saveAuthToken(context, deviceToken.trim())
                                        com.example.data.security.SecurityManager.saveDeviceToken(context, deviceToken.trim())
                                    }
                                    AppConfig.setServer(serverIp, serverPort)
                                    com.example.data.security.SecurityManager.saveServerConfig(context, serverIp, serverPort)
                                    WebSocketManager.disconnect()
                                    WebSocketManager.connect()
                                    scope.launch { viewModel.refreshMetrics() }
                                },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = DashPurpleSecondary)
                            ) {
                                Text("Save & Connect", color = dashColors().surface, fontWeight = FontWeight.Bold)
                            }
                        }

                        // Test result
                        if (testResult != null) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(
                                        if (isTestSuccess) DashSuccessGreen.copy(alpha = 0.1f)
                                        else DashErrorRed.copy(alpha = 0.1f)
                                    )
                                    .padding(12.dp)
                            ) {
                                Text(
                                    text = testResult!!,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 12.sp,
                                    color = if (isTestSuccess) DashSuccessGreen else DashErrorRed
                                )
                            }
                        }

                        // Help text
                        Text(
                            text = "\nTip: Use '10.0.2.2' for Android emulator, or your PC's LAN IP for physical device. Find your PC's IP with 'ipconfig' in Command Prompt.",
                            style = MaterialTheme.typography.bodySmall,
                            color = dashColors().textMuted,
                            fontSize = 10.sp
                        )
                    }
                }
            }

            // Device Info
            item {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = "DEVICE INFO",
                            style = MaterialTheme.typography.labelSmall,
                            color = dashColors().textMuted,
                            letterSpacing = 1.2.sp
                        )

                        DeviceInfoRow(
                            icon = Icons.Default.PhoneAndroid,
                            name = "This Device (Android)",
                            status = "Companion",
                            statusColor = DashCyanPrimary
                        )
                        DeviceInfoRow(
                            icon = Icons.Default.Computer,
                            name = systemMetrics.pcName,
                            status = if (systemMetrics.isPcOnline) "Online" else "Offline",
                            statusColor = if (systemMetrics.isPcOnline) DashSuccessGreen else DashErrorRed
                        )
                        DeviceInfoRow(
                            icon = Icons.Default.Security,
                            name = "Auth",
                            status = if (AppConfig.isAuthenticated) "Token Valid" else "No Token",
                            statusColor = if (AppConfig.isAuthenticated) DashSuccessGreen else DashErrorRed
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row {
        Text(
            text = "$label: ",
            fontFamily = FontFamily.Monospace,
            fontSize = 11.sp,
            color = dashColors().textMuted
        )
        Text(
            text = value,
            fontFamily = FontFamily.Monospace,
            fontSize = 11.sp,
            color = DashCyanPrimary
        )
    }
}

@Composable
private fun DeviceInfoRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    name: String,
    status: String,
    statusColor: Color
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = statusColor,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = name,
                style = MaterialTheme.typography.bodyMedium,
                color = dashColors().textPrimary
            )
        }
        Box(
            modifier = Modifier
                .clip(CircleShape)
                .background(statusColor.copy(alpha = 0.12f))
                .padding(horizontal = 8.dp, vertical = 3.dp)
        ) {
            Text(
                text = status,
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp,
                color = statusColor
            )
        }
    }
}
