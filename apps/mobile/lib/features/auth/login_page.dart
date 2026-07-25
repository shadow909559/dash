import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/dash_theme.dart';
import '../../core/widgets/glassmorphism.dart';
import '../../core/widgets/ai_core.dart';
import 'providers/auth_provider.dart';

/// Premium futuristic Login Page — inspired by JARVIS / Iron Man HUD.
/// Features glass panels, animated AI core, particle background, and glow effects.
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});
  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _usernameController = TextEditingController();
  bool _isRegisterMode = false;
  bool _obscurePassword = true;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(seconds: 3),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _usernameController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    if (_isRegisterMode) {
      print("Registration form validated successfully.");
    }

    final email = _emailController.text.trim();
    final password = _passwordController.text;

    if (_isRegisterMode) {
      await ref.read(authProvider.notifier).register(
        email: email,
        username: _usernameController.text.trim(),
        password: password,
      );
    } else {
      await ref
          .read(authProvider.notifier)
          .login(email: email, password: password);
    }

    if (mounted &&
        ref.read(authProvider).status == AuthStatus.authenticated) {
      context.go(AppRoutes.dashboard);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    return Scaffold(
      backgroundColor: DashColors.carbonBlack,
      body: Stack(
        children: [
          // Animated background glow
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                final opacity = 0.03 + _pulseController.value * 0.03;
                return Container(
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      colors: [
                        DashColors.electricBlue.withValues(alpha: opacity),
                        DashColors.purpleGlow.withValues(
                            alpha: opacity * 0.5),
                        Colors.transparent,
                      ],
                      center: Alignment.center,
                      radius: 1.2,
                    ),
                  ),
                );
              },
            ),
          ),
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: GlassPanel(
                    padding: const EdgeInsets.all(32),
                    borderRadius: 24,
                    child: Form(
                      key: _formKey,
                      autovalidateMode: AutovalidateMode.onUserInteraction,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // AI Core
                          const AICoreWithStatus(
                            state: AIState.idle,
                            size: 100,
                            statusText: 'DASH AI OS',
                          ),
                          const SizedBox(height: 24),
                          // Title
                          Text(
                            _isRegisterMode
                                ? 'Initialize Access'
                                : 'Authenticate',
                            style: DashTypography.titleLarge.copyWith(
                              color: DashColors.pureWhite,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 1,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _isRegisterMode
                                ? 'Create your neural signature'
                                : 'Access your neural interface',
                            style: DashTypography.bodyMedium.copyWith(
                              color: DashColors.textGray,
                            ),
                          ),
                          const SizedBox(height: 32),
                          // Error
                          if (authState.errorMessage != null)
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(12),
                              margin: const EdgeInsets.only(bottom: 16),
                              decoration: BoxDecoration(
                                color: DashColors.errorRed.withValues(
                                    alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                    color: DashColors.errorRed.withValues(
                                        alpha: 0.2)),
                              ),
                              child: Row(children: [
                                const Icon(Icons.error_outline,
                                    color: DashColors.errorRed, size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    authState.errorMessage!,
                                    style: const TextStyle(
                                        color: DashColors.errorRed,
                                        fontSize: 12),
                                  ),
                                ),
                              ]),
                            ),
                          // Username (register)
                          if (_isRegisterMode) ...[
                            GlassInput(
                              controller: _usernameController,
                              hintText: 'Username',
                              prefixIcon: const Icon(Icons.person_outline,
                                  color: DashColors.textGray, size: 20),
                              validator: (v) => v == null || v.trim().isEmpty
                                  ? 'Required'
                                  : v.trim().length < 3
                                      ? 'Min 3 chars'
                                      : null,
                            ),
                            const SizedBox(height: 16),
                          ],
                          // Email
                          GlassInput(
                            controller: _emailController,
                            hintText: 'Email',
                            keyboardType: TextInputType.emailAddress,
                            prefixIcon: const Icon(Icons.email_outlined,
                                color: DashColors.textGray, size: 20),
                            validator: (v) => v == null || v.trim().isEmpty
                                ? 'Required'
                                : !v.contains('@')
                                    ? 'Invalid email'
                                    : null,
                          ),
                          const SizedBox(height: 16),
                          // Password
                          GlassInput(
                            controller: _passwordController,
                            hintText: 'Password',
                            obscureText: _obscurePassword,
                            prefixIcon: const Icon(Icons.lock_outline,
                                color: DashColors.textGray, size: 20),
                            suffixIcon: IconButton(
                              icon: Icon(
                                _obscurePassword
                                    ? Icons.visibility_off
                                    : Icons.visibility,
                                color: DashColors.textGray,
                                size: 20,
                              ),
                              onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword),
                            ),
                            validator: (v) {
                              if (v == null || v.isEmpty) return 'Required';
                              if (_isRegisterMode && v.length < 8) {
                                return 'Min 8 chars';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 24),
                          // Submit Button
                          GlassButton(
                            onPressed: authState.isLoading ? null : _submit,
                            width: double.infinity,
                            padding:
                                const EdgeInsets.symmetric(vertical: 16),
                            child: authState.isLoading
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: DashColors.pureWhite),
                                  )
                                : Text(
                                    _isRegisterMode
                                        ? 'Initialize'
                                        : 'Access Interface',
                                    style: DashTypography.labelLarge.copyWith(
                                        color: DashColors.pureWhite,
                                        letterSpacing: 1),
                                  ),
                          ),
                          const SizedBox(height: 16),
                          // Toggle
                          TextButton(
                            onPressed: () {
                              setState(
                                  () => _isRegisterMode = !_isRegisterMode);
                              ref
                                  .read(authProvider.notifier)
                                  .clearError();
                            },
                            child: Text(
                              _isRegisterMode
                                  ? 'Already have access? Sign in'
                                  : 'No neural link? Initialize',
                              style: TextStyle(
                                  color: DashColors.electricBlue,
                                  fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
