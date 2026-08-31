package com.example

import android.os.Bundle
import androidx.activity.ComponentActivity
import com.example.data.config.AppConfig
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.ui.components.DashBottomNav
import com.example.ui.components.DashTopBar
import com.example.ui.components.NavDestination
import com.example.ui.screens.ActivityScreen
import com.example.ui.screens.ChatScreen
import com.example.ui.screens.HomeScreen
import com.example.ui.screens.MoreScreen
import com.example.ui.screens.MoreSubScreen
import com.example.ui.screens.VoiceScreen
import com.example.ui.screens.subscreens.AiProvidersSubScreen
import com.example.ui.screens.subscreens.OllamaChatScreen
import com.example.ui.screens.subscreens.AppLauncherSubScreen
import com.example.ui.screens.subscreens.ApprovalsSubScreen
import com.example.ui.screens.subscreens.CloudAwsSubScreen
import com.example.ui.screens.subscreens.CommandCenterScreen
import com.example.ui.screens.subscreens.ComputerControlSubScreen
import com.example.ui.screens.subscreens.DevicePairingSubScreen
import com.example.ui.screens.subscreens.RemoteControlSubScreen
import com.example.ui.screens.subscreens.DeviceStatusSubScreen
import com.example.ui.screens.subscreens.NotificationHistorySubScreen
import com.example.ui.screens.subscreens.DiagnosticsSubScreen
import com.example.ui.screens.subscreens.FileBrowserSubScreen
import com.example.ui.screens.subscreens.KnowledgeResearchSubScreen
import com.example.ui.screens.subscreens.MemorySubScreen
import com.example.ui.screens.subscreens.PlannerSubScreen
import com.example.ui.screens.subscreens.ProjectsSubScreen
import com.example.ui.screens.subscreens.WindowManagerSubScreen
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashTheme
import com.example.ui.components.ProvideHapticManager
import com.example.ui.theme.dashColors
import com.example.ui.theme.ThemeMode
import com.example.ui.theme.ThemePreference
import com.example.ui.viewmodel.DashViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Start foreground service now that app is in foreground (Android 12+ requirement)
        if (AppConfig.isAuthenticated) {
            try {
                com.example.data.connection.DashForegroundService.start(this)
            } catch (e: Exception) {
                android.util.Log.w("DASH", "Failed to start foreground service: ${e.message}")
            }
        }

        setContent {
            val themeMode by ThemePreference.themeMode.collectAsState()
            val isDark = when (themeMode) {
                ThemeMode.DARK -> true
                ThemeMode.LIGHT -> false
                ThemeMode.SYSTEM -> androidx.compose.foundation.isSystemInDarkTheme()
            }
            DashTheme(isDarkTheme = isDark) {
                ProvideHapticManager {
                    DashApp()
                }
            }
        }
    }
}

@Composable
fun DashApp() {
    val viewModel: DashViewModel = viewModel()
    val navController: NavHostController = rememberNavController()

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route ?: "home"

    val isSafeMode by viewModel.isSafeModeActive.collectAsState()

    val currentDestination = when (currentRoute) {
        "home" -> NavDestination.HOME
        "chat" -> NavDestination.CHAT
        "voice" -> NavDestination.VOICE
        "activity" -> NavDestination.ACTIVITY
        "more" -> NavDestination.MORE
        else -> NavDestination.HOME
    }

    val isFullScreenVoice = currentRoute == "voice"

    Scaffold(
        modifier = Modifier
            .fillMaxSize()
            .background(dashColors().background),
        containerColor = dashColors().background,
        topBar = {
            if (!isFullScreenVoice) {
                DashTopBar(
                    isSafeMode = isSafeMode,
                    isPcLinked = true,
                    onSearchClick = {
                        navController.navigate("chat") {
                            popUpTo("home") { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onProfileClick = {
                        navController.navigate("pairing")
                    }
                )
            }
        },
        bottomBar = {
            if (!isFullScreenVoice) {
                DashBottomNav(
                    currentDestination = currentDestination,
                    onNavigate = { destination ->
                        if (destination == NavDestination.VOICE) {
                            viewModel.startVoiceInteraction()
                            navController.navigate("voice")
                        } else {
                            navController.navigate(destination.route) {
                                popUpTo("home") { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    }
                )
            }
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(dashColors().background)
        ) {
            NavHost(
                navController = navController,
                startDestination = "home"
            ) {
                // ── Tab transition helpers ──
                val tabRoutes = listOf("home", "chat", "activity", "more")
                fun tabEnter(): EnterTransition {
                    val from = navBackStackEntry?.destination?.route ?: "home"
                    val fromIdx = tabRoutes.indexOf(from).coerceAtLeast(0)
                    val toIdx = tabRoutes.indexOf(navController.currentDestination?.route).coerceAtLeast(0)
                    return if (toIdx >= fromIdx)
                        slideInHorizontally(animationSpec = tween(250)) { it / 4 } + fadeIn(animationSpec = tween(250))
                    else
                        slideInHorizontally(animationSpec = tween(250)) { -it / 4 } + fadeIn(animationSpec = tween(250))
                }
                fun tabExit(): ExitTransition {
                    val from = navBackStackEntry?.destination?.route ?: "home"
                    val fromIdx = tabRoutes.indexOf(from).coerceAtLeast(0)
                    val toIdx = tabRoutes.indexOf(navController.currentDestination?.route).coerceAtLeast(0)
                    return if (toIdx >= fromIdx)
                        slideOutHorizontally(animationSpec = tween(250)) { -it / 4 } + fadeOut(animationSpec = tween(200))
                    else
                        slideOutHorizontally(animationSpec = tween(250)) { it / 4 } + fadeOut(animationSpec = tween(200))
                }

                // Primary Tabs
                composable(
                    "home",
                    enterTransition = { tabEnter() },
                    exitTransition = { tabExit() },
                    popEnterTransition = { tabEnter() },
                    popExitTransition = { tabExit() }
                ) {
                    HomeScreen(
                        viewModel = viewModel,
                        onNavigate = { route ->
                            if (route == "voice") {
                                viewModel.startVoiceInteraction()
                            }
                            navController.navigate(route) {
                                popUpTo("home") { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }

                composable(
                    "chat",
                    enterTransition = { tabEnter() },
                    exitTransition = { tabExit() },
                    popEnterTransition = { tabEnter() },
                    popExitTransition = { tabExit() }
                ) {
                    ChatScreen(
                        viewModel = viewModel,
                        onOpenVoice = {
                            viewModel.startVoiceInteraction()
                            navController.navigate("voice")
                        }
                    )
                }

                composable(
                    "voice",
                    enterTransition = { fadeIn(animationSpec = tween(300)) + slideInVertically(animationSpec = tween(300)) { it / 3 } },
                    exitTransition = { fadeOut(animationSpec = tween(250)) + slideOutVertically(animationSpec = tween(250)) { it / 3 } },
                    popEnterTransition = { fadeIn(animationSpec = tween(300)) + slideInVertically(animationSpec = tween(300)) { it / 3 } },
                    popExitTransition = { fadeOut(animationSpec = tween(250)) + slideOutVertically(animationSpec = tween(250)) { it / 3 } }
                ) {
                    VoiceScreen(
                        viewModel = viewModel,
                        onClose = {
                            viewModel.stopVoiceInteraction()
                            navController.popBackStack()
                        }
                    )
                }

                composable(
                    "activity",
                    enterTransition = { tabEnter() },
                    exitTransition = { tabExit() },
                    popEnterTransition = { tabEnter() },
                    popExitTransition = { tabExit() }
                ) {
                    ActivityScreen(viewModel = viewModel)
                }

                composable(
                    "more",
                    enterTransition = { tabEnter() },
                    exitTransition = { tabExit() },
                    popEnterTransition = { tabEnter() },
                    popExitTransition = { tabExit() }
                ) {
                    MoreScreen(
                        viewModel = viewModel,
                        onNavigateSub = { subScreen ->
                            when (subScreen) {
                                MoreSubScreen.COMPUTER_CONTROL -> navController.navigate("computer_control")
                                MoreSubScreen.PROJECTS -> navController.navigate("projects")
                                MoreSubScreen.APPROVALS -> navController.navigate("approvals")
                                MoreSubScreen.MEMORY -> navController.navigate("memory")
                                MoreSubScreen.PLANNER -> navController.navigate("planner")
                                MoreSubScreen.KNOWLEDGE_RESEARCH -> navController.navigate("knowledge")
                                MoreSubScreen.DEVICE_PAIRING -> navController.navigate("pairing")
                                MoreSubScreen.REMOTE_CONTROL -> navController.navigate("remote_control")
                                MoreSubScreen.CLOUD_AWS -> navController.navigate("cloud_aws")
                                MoreSubScreen.DIAGNOSTICS -> navController.navigate("diagnostics")
                                MoreSubScreen.NOTIFICATION_HISTORY -> navController.navigate("notification_history")
                                MoreSubScreen.AI_PROVIDERS -> navController.navigate("ai_providers")
                                MoreSubScreen.FILE_BROWSER -> navController.navigate("file_browser")
                                MoreSubScreen.WINDOW_MANAGER -> navController.navigate("window_manager")
                                MoreSubScreen.APP_LAUNCHER -> navController.navigate("app_launcher")
                                MoreSubScreen.DEVICE_STATUS -> navController.navigate("device_status")
                                MoreSubScreen.OLLAMA_CHAT -> navController.navigate("ollama_chat")
                                else -> {}
                            }
                        }
                    )
                }

                // ── Sub-screen push-from-bottom transition ──
                fun subEnter(): EnterTransition = slideInVertically(animationSpec = tween(300)) { it / 5 } + fadeIn(animationSpec = tween(250))
                fun subExit(): ExitTransition = slideOutVertically(animationSpec = tween(250)) { it / 5 } + fadeOut(animationSpec = tween(200))

                // Subscreens
                composable(
                    "computer_control",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    ComputerControlSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "approvals",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    ApprovalsSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "projects",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    ProjectsSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() },
                        onAskDash = { prompt ->
                            viewModel.sendMessage(prompt)
                            navController.navigate("chat")
                        }
                    )
                }

                composable(
                    "memory",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    MemorySubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "planner",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    PlannerSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "knowledge",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    KnowledgeResearchSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() },
                        onAskDash = { prompt ->
                            viewModel.sendMessage(prompt)
                            navController.navigate("chat")
                        }
                    )
                }

                composable(
                    "remote_control",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    RemoteControlSubScreen(
                        onBack = { navController.popBackStack() }
                    )
                }
                composable(
                    "pairing",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    DevicePairingSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "cloud_aws",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    CloudAwsSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "diagnostics",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    DiagnosticsSubScreen(
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "notification_history",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    NotificationHistorySubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "ai_providers",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    AiProvidersSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                // New subscreens
                composable(
                    "file_browser",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    FileBrowserSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "window_manager",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    WindowManagerSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "app_launcher",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    AppLauncherSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "device_status",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    DeviceStatusSubScreen(
                        viewModel = viewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    "ollama_chat",
                    enterTransition = { subEnter() },
                    exitTransition = { subExit() },
                    popEnterTransition = { subEnter() },
                    popExitTransition = { subExit() }
                ) {
                    OllamaChatScreen(
                        onBack = { navController.popBackStack() }
                    )
                }
            }
        }
    }
}
