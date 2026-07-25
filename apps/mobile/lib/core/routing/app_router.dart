import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/automation/automation_page.dart';
import '../../features/automation/automation_history_page.dart';
import '../../features/desktop/desktop_page.dart';
import '../../features/voice/voice_page.dart';
import '../../features/vision/vision_page.dart';
import '../../features/files/file_manager_page.dart';
import '../../features/about/about_page.dart';
import '../../features/auth/login_page.dart';
import '../../features/auth/register_page.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/chat/chat_page.dart';
import '../../features/chat/conversation_details_page.dart';
import '../../features/chat/conversation_history_page.dart';
import '../../features/dashboard/dashboard_page.dart';
import '../../features/help/help_page.dart';
import '../../features/memory/memory_page.dart';
import '../../features/memory/memory_details_page.dart';
import '../../features/notifications/notification_center_page.dart';
import '../../features/planner/calendar_page.dart';
import '../../features/planner/goal_details_page.dart';
import '../../features/planner/goals_page.dart';
import '../../features/planner/planner_page.dart';
import '../../features/plugins/plugin_details_page.dart';
import '../../features/plugins/plugins_page.dart';
import '../../features/profile/profile_page.dart';
import '../../features/projects/project_manager_page.dart';
import '../../features/search/search_page.dart';
import '../../features/settings/settings_page.dart';
import '../../features/splash/splash_page.dart';
import '../../features/tasks/task_details_page.dart';
import '../../features/tasks/tasks_page.dart';
import '../../features/workspace/workspace_page.dart';
import '../../shared/widgets/app_shell.dart';
import 'app_routes.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final rootNavigatorKey = GlobalKey<NavigatorState>();

  final router = GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: AppRoutes.splash,
    redirect: (context, state) {
      final authState = ref.read(authProvider);

      // Allow splash and login to proceed without redirect.
      final path = state.uri.path;
      final isAuthRoute = path == AppRoutes.splash || path == AppRoutes.login;

      if (authState.status == AuthStatus.authenticated) {
        // Authenticated users should not see login or splash.
        if (isAuthRoute) return AppRoutes.dashboard;
        return null;
      }

      // Auth status is still unknown — let the splash page handle it.
      if (authState.status == AuthStatus.unknown) return null;

      // Unauthenticated: protect all shell routes.
      if (!isAuthRoute) return AppRoutes.login;

      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        name: 'splash',
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: AppRoutes.register,
        name: 'register',
        builder: (context, state) => const RegisterPage(),
      ),
      GoRoute(
        path: AppRoutes.login,
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),
      ShellRoute(
        builder: (context, state, child) {
          return AppShell(
            location: state.uri.path,
            child: child,
          );
        },
        routes: [
          GoRoute(
            path: AppRoutes.dashboard,
            name: 'dashboard',
            builder: (context, state) => const DashboardPage(),
          ),
          GoRoute(
            path: AppRoutes.chat,
            name: 'chat',
            builder: (context, state) => const ChatPage(),
          ),
          GoRoute(
            path: AppRoutes.conversationHistory,
            name: 'conversation-history',
            builder: (context, state) => const ConversationHistoryPage(),
          ),
          GoRoute(
            path: '${AppRoutes.conversationDetails}/:conversationId',
            name: 'conversation-details',
            builder: (context, state) {
              final id = state.pathParameters['conversationId']!;
              return ConversationDetailsPage(conversationId: id);
            },
          ),
          GoRoute(
            path: AppRoutes.settings,
            name: 'settings',
            builder: (context, state) => const SettingsPage(),
          ),
          GoRoute(
            path: AppRoutes.memory,
            name: 'memory',
            builder: (context, state) => const MemoryPage(),
          ),
          GoRoute(
            path: AppRoutes.memoryDetails,
            name: 'memoryDetails',
            builder: (context, state) {
              final memoryId = state.pathParameters['memoryId'] ?? '';
              return MemoryDetailsPage(memoryId: memoryId);
            },
          ),
          GoRoute(
            path: AppRoutes.about,
            name: 'about',
            builder: (context, state) => const AboutPage(),
          ),
          GoRoute(
            path: AppRoutes.workspace,
            name: 'workspace',
            builder: (context, state) => const WorkspacePage(),
          ),
          GoRoute(
            path: AppRoutes.projects,
            name: 'projects',
            builder: (context, state) => const ProjectManagerPage(),
          ),
          GoRoute(
            path: AppRoutes.notifications,
            name: 'notifications',
            builder: (context, state) => const NotificationCenterPage(),
          ),
          GoRoute(
            path: AppRoutes.plugins,
            name: 'plugins',
            builder: (context, state) => const PluginsPage(),
          ),
          GoRoute(
            path: '${AppRoutes.pluginDetails}/:pluginId',
            name: 'pluginDetails',
            builder: (context, state) {
              final pluginId = state.pathParameters['pluginId'] ?? '';
              return PluginDetailsPage(pluginId: pluginId);
            },
          ),
          GoRoute(
            path: AppRoutes.search,
            name: 'search',
            builder: (context, state) => const SearchPage(),
          ),
          GoRoute(
            path: AppRoutes.profile,
            name: 'profile',
            builder: (context, state) => const ProfilePage(),
          ),
          GoRoute(
            path: AppRoutes.help,
            name: 'help',
            builder: (context, state) => const HelpPage(),
          ),
          GoRoute(
            path: AppRoutes.planner,
            name: 'planner',
            builder: (context, state) => const PlannerPage(),
          ),
          GoRoute(
            path: AppRoutes.calendar,
            name: 'calendar',
            builder: (context, state) => const CalendarPage(),
          ),
          GoRoute(
            path: AppRoutes.goals,
            name: 'goals',
            builder: (context, state) => const GoalsPage(),
          ),
          GoRoute(
            path: '${AppRoutes.goalDetails}/:goalId',
            name: 'goalDetails',
            builder: (context, state) {
              final goalId = state.pathParameters['goalId'] ?? '';
              return GoalDetailsPage(goalId: goalId);
            },
          ),
          GoRoute(
            path: AppRoutes.tasks,
            name: 'tasks',
            builder: (context, state) => const TasksPage(),
          ),
          GoRoute(
            path: '${AppRoutes.taskDetails}/:taskId',
            name: 'taskDetails',
            builder: (context, state) {
              final taskId = state.pathParameters['taskId'] ?? '';
              return TaskDetailsPage(taskId: taskId);
            },
          ),
          GoRoute(
            path: AppRoutes.automation,
            name: 'automation',
            builder: (context, state) => const AutomationPage(),
          ),
          GoRoute(
            path: AppRoutes.desktop,
            name: 'desktop',
            builder: (context, state) => const DesktopPage(),
          ),
          GoRoute(
            path: AppRoutes.voice,
            name: 'voice',
            builder: (context, state) => const VoicePage(),
          ),
          GoRoute(
            path: AppRoutes.vision,
            name: 'vision',
            builder: (context, state) => const VisionPage(),
          ),
          GoRoute(
            path: AppRoutes.files,
            name: 'files',
            builder: (context, state) => const FileManagerPage(),
          ),
          GoRoute(
            path: '${AppRoutes.automationHistory}/:automationId',
            name: 'automationHistory',
            builder: (context, state) {
              final automationId = state.pathParameters['automationId'] ?? '';
              return AutomationHistoryPage(automationId: automationId);
            },
          ),
        ],
      ),
    ],
  );

  ref.onDispose(router.dispose);
  return router;
});
