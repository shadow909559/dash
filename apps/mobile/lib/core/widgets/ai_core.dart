import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/dash_theme.dart';

/// AI Core States - represents different states of the AI system
enum AIState {
  idle,
  listening,
  thinking,
  speaking,
  streaming,
  processing,
  error,
}

/// AI Core Widget - The centerpiece of DASH AI Operating System
/// Inspired by JARVIS, Iron Man HUD, and futuristic AI interfaces
/// Features animated circles, particle system, and state-based animations
class AICore extends StatefulWidget {
  final AIState state;
  final double size;
  final VoidCallback? onTap;
  final bool showParticles;
  final bool showRings;
  final bool showGlow;

  const AICore({
    super.key,
    this.state = AIState.idle,
    this.size = 200,
    this.onTap,
    this.showParticles = true,
    this.showRings = true,
    this.showGlow = true,
  });

  @override
  State<AICore> createState() => _AICoreState();
}

class _AICoreState extends State<AICore>
    with TickerProviderStateMixin {
  late AnimationController _outerRingController;
  late AnimationController _middleRingController;
  late AnimationController _innerRingController;
  late AnimationController _coreController;
  late AnimationController _pulseController;
  late AnimationController _particleController;

  @override
  void initState() {
    super.initState();
    _outerRingController = AnimationController(
      duration: DashDuration.rotate,
      vsync: this,
    )..repeat();
    
    _middleRingController = AnimationController(
      duration: const Duration(seconds: 15),
      vsync: this,
    )..repeat(reverse: true);
    
    _innerRingController = AnimationController(
      duration: const Duration(seconds: 10),
      vsync: this,
    )..repeat();
    
    _coreController = AnimationController(
      duration: DashDuration.breathe,
      vsync: this,
    )..repeat(reverse: true);
    
    _pulseController = AnimationController(
      duration: DashDuration.pulse,
      vsync: this,
    )..repeat();
    
    _particleController = AnimationController(
      duration: const Duration(seconds: 20),
      vsync: this,
    )..repeat();
  }

  @override
  void didUpdateWidget(AICore oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state != oldWidget.state) {
      _updateStateAnimation();
    }
  }

  void _updateStateAnimation() {
    switch (widget.state) {
      case AIState.listening:
        _outerRingController.duration = const Duration(seconds: 8);
        _middleRingController.duration = const Duration(seconds: 6);
        _innerRingController.duration = const Duration(seconds: 4);
        _coreController.duration = const Duration(milliseconds: 800);
        break;
      case AIState.thinking:
        _outerRingController.duration = const Duration(seconds: 3);
        _middleRingController.duration = const Duration(seconds: 2);
        _innerRingController.duration = const Duration(seconds: 1);
        _coreController.duration = const Duration(milliseconds: 500);
        break;
      case AIState.speaking:
      case AIState.streaming:
        _outerRingController.duration = const Duration(seconds: 5);
        _middleRingController.duration = const Duration(seconds: 4);
        _innerRingController.duration = const Duration(seconds: 3);
        _coreController.duration = const Duration(milliseconds: 600);
        break;
      case AIState.error:
        _outerRingController.duration = const Duration(milliseconds: 500);
        _middleRingController.duration = const Duration(milliseconds: 400);
        _innerRingController.duration = const Duration(milliseconds: 300);
        _coreController.duration = const Duration(milliseconds: 300);
        break;
      default:
        _outerRingController.duration = DashDuration.rotate;
        _middleRingController.duration = const Duration(seconds: 15);
        _innerRingController.duration = const Duration(seconds: 10);
        _coreController.duration = DashDuration.breathe;
    }
    
    _outerRingController.repeat();
    _middleRingController.repeat(reverse: true);
    _innerRingController.repeat();
    _coreController.repeat(reverse: true);
  }

  @override
  void dispose() {
    _outerRingController.dispose();
    _middleRingController.dispose();
    _innerRingController.dispose();
    _coreController.dispose();
    _pulseController.dispose();
    _particleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap,
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Glow effect
            if (widget.showGlow) _buildGlow(),
            
            // Particles
            if (widget.showParticles) _buildParticles(),
            
            // Outer Ring
            if (widget.showRings) _buildOuterRing(),
            
            // Middle Ring
            if (widget.showRings) _buildMiddleRing(),
            
            // Inner Ring
            if (widget.showRings) _buildInnerRing(),
            
            // Energy Core
            _buildCore(),
            
            // Center Pulse
            _buildCenterPulse(),
          ],
        ),
      ),
    );
  }

  Widget _buildGlow() {
    final glowColor = _getStateColor();
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final pulseValue = (_pulseController.value * 2 - 1).abs();
        return Container(
          width: widget.size * 1.2,
          height: widget.size * 1.2,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                glowColor.withValues(alpha: 0.3 + pulseValue * 0.2),
                glowColor.withValues(alpha: 0.1),
                Colors.transparent,
              ],
              stops: const [0.0, 0.5, 1.0],
            ),
          ),
        );
      },
    );
  }

  Widget _buildParticles() {
    return AnimatedBuilder(
      animation: _particleController,
      builder: (context, child) {
        return CustomPaint(
          size: Size(widget.size, widget.size),
          painter: _ParticlePainter(
            animation: _particleController,
            color: _getStateColor(),
            particleCount: 30,
          ),
        );
      },
    );
  }

  Widget _buildOuterRing() {
    return AnimatedBuilder(
      animation: _outerRingController,
      builder: (context, child) {
        return Transform.rotate(
          angle: _outerRingController.value * 2 * math.pi,
          child: CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _RingPainter(
              radius: widget.size * 0.45,
              strokeWidth: 2,
              color: _getStateColor().withValues(alpha: 0.5),
              segments: 12,
              dashPattern: const [10, 15],
            ),
          ),
        );
      },
    );
  }

  Widget _buildMiddleRing() {
    return AnimatedBuilder(
      animation: _middleRingController,
      builder: (context, child) {
        return Transform.rotate(
          angle: -_middleRingController.value * 2 * math.pi,
          child: CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _RingPainter(
              radius: widget.size * 0.35,
              strokeWidth: 3,
              color: _getStateColor().withValues(alpha: 0.7),
              segments: 8,
              dashPattern: const [20, 10],
            ),
          ),
        );
      },
    );
  }

  Widget _buildInnerRing() {
    return AnimatedBuilder(
      animation: _innerRingController,
      builder: (context, child) {
        return Transform.rotate(
          angle: _innerRingController.value * 2 * math.pi,
          child: CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _RingPainter(
              radius: widget.size * 0.25,
              strokeWidth: 4,
              color: _getStateColor(),
              segments: 6,
              dashPattern: const [15, 5],
            ),
          ),
        );
      },
    );
  }

  Widget _buildCore() {
    return AnimatedBuilder(
      animation: _coreController,
      builder: (context, child) {
        final scale = 0.8 + _coreController.value * 0.2;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: widget.size * 0.15,
            height: widget.size * 0.15,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  _getStateColor(),
                  _getStateColor().withValues(alpha: 0.5),
                  _getStateColor().withValues(alpha: 0.2),
                ],
                stops: const [0.0, 0.5, 1.0],
              ),
              boxShadow: [
                BoxShadow(
                  color: _getStateColor().withValues(alpha: 0.5),
                  blurRadius: 20,
                  spreadRadius: 5,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildCenterPulse() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final pulseValue = _pulseController.value;
        final pulseSize = widget.size * 0.05 + pulseValue * widget.size * 0.1;
        final pulseOpacity = 1.0 - pulseValue;
        
        return Container(
          width: pulseSize,
          height: pulseSize,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: _getStateColor().withValues(alpha: pulseOpacity * 0.5),
          ),
        ).animate(onPlay: (controller) => controller.repeat()).fadeIn(
          duration: DashDuration.fast,
        ).scale(
          begin: const Offset(0.5, 0.5),
          end: const Offset(2.0, 2.0),
          duration: DashDuration.pulse,
          curve: DashCurves.easeOut,
        ).fadeOut(
          duration: DashDuration.pulse,
        );
      },
    );
  }

  Color _getStateColor() {
    switch (widget.state) {
      case AIState.idle:
        return DashColors.electricBlue;
      case AIState.listening:
        return DashColors.neonCyan;
      case AIState.thinking:
        return DashColors.purpleGlow;
      case AIState.speaking:
        return DashColors.energyGreen;
      case AIState.streaming:
        return DashColors.arcReactorBlue;
      case AIState.processing:
        return DashColors.warningAmber;
      case AIState.error:
        return DashColors.errorRed;
    }
  }
}

/// Custom painter for animated rings
class _RingPainter extends CustomPainter {
  final double radius;
  final double strokeWidth;
  final Color color;
  final int segments;
  final List<double> dashPattern;

  _RingPainter({
    required this.radius,
    required this.strokeWidth,
    required this.color,
    required this.segments,
    required this.dashPattern,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final segmentAngle = 2 * math.pi / segments;
    
    for (int i = 0; i < segments; i++) {
      final startAngle = i * segmentAngle;
      final endAngle = startAngle + segmentAngle * 0.7;
      
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        endAngle - startAngle,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter oldDelegate) {
    return oldDelegate.radius != radius ||
        oldDelegate.color != color ||
        oldDelegate.segments != segments;
  }
}

/// Custom painter for particles
class _ParticlePainter extends CustomPainter {
  final Animation<double> animation;
  final Color color;
  final int particleCount;

  _ParticlePainter({
    required this.animation,
    required this.color,
    required this.particleCount,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()
      ..color = color.withValues(alpha: 0.6)
      ..style = PaintingStyle.fill;

    for (int i = 0; i < particleCount; i++) {
      final angle = (i / particleCount) * 2 * math.pi + animation.value * 2 * math.pi;
      final distance = size.width * 0.3 + (animation.value + i / particleCount) % 1.0 * size.width * 0.2;
      final x = center.dx + math.cos(angle) * distance;
      final y = center.dy + math.sin(angle) * distance;
      final particleSize = 2.0 + math.sin(animation.value * 2 * math.pi + i) * 1.5;

      canvas.drawCircle(
        Offset(x, y),
        particleSize,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_ParticlePainter oldDelegate) {
    return oldDelegate.animation.value != animation.value;
  }
}

/// Mini AI Core for compact displays
class MiniAICore extends StatelessWidget {
  final AIState state;
  final double size;
  final VoidCallback? onTap;

  const MiniAICore({
    super.key,
    this.state = AIState.idle,
    this.size = 60,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return AICore(
      state: state,
      size: size,
      onTap: onTap,
      showParticles: false,
      showRings: true,
      showGlow: true,
    );
  }
}

/// AI Core with status indicator
class AICoreWithStatus extends StatelessWidget {
  final AIState state;
  final double size;
  final String? statusText;
  final VoidCallback? onTap;

  const AICoreWithStatus({
    super.key,
    this.state = AIState.idle,
    this.size = 200,
    this.statusText,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AICore(
          state: state,
          size: size,
          onTap: onTap,
        ),
        if (statusText != null) ...[
          const SizedBox(height: 16),
          Text(
            statusText!,
            style: DashTypography.labelMedium.copyWith(
              color: _getStateColor(),
              letterSpacing: 1.5,
            ),
          ).animate().fadeIn(duration: DashDuration.normal),
        ],
      ],
    );
  }

  Color _getStateColor() {
    switch (state) {
      case AIState.idle:
        return DashColors.electricBlue;
      case AIState.listening:
        return DashColors.neonCyan;
      case AIState.thinking:
        return DashColors.purpleGlow;
      case AIState.speaking:
        return DashColors.energyGreen;
      case AIState.streaming:
        return DashColors.arcReactorBlue;
      case AIState.processing:
        return DashColors.warningAmber;
      case AIState.error:
        return DashColors.errorRed;
    }
  }
}
