import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/dash_theme.dart';

/// Animated background types
enum BackgroundType {
  neuralGrid,
  particles,
  energyLines,
  constellation,
  circuitPattern,
  holographic,
}

/// Premium animated background system for DASH AI Operating System
class AnimatedBackground extends StatefulWidget {
  final BackgroundType type;
  final Color? primaryColor;
  final Color? secondaryColor;
  final double opacity;
  final bool animate;

  const AnimatedBackground({
    super.key,
    this.type = BackgroundType.neuralGrid,
    this.primaryColor,
    this.secondaryColor,
    this.opacity = 0.3,
    this.animate = true,
  });

  @override
  State<AnimatedBackground> createState() => _AnimatedBackgroundState();
}

class _AnimatedBackgroundState extends State<AnimatedBackground>
    with TickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(seconds: 30),
      vsync: this,
    );
    if (widget.animate) {
      _controller.repeat();
    }
  }

  @override
  void didUpdateWidget(AnimatedBackground oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.animate != oldWidget.animate) {
      if (widget.animate) {
        _controller.repeat();
      } else {
        _controller.stop();
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: widget.opacity,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          return CustomPaint(
            size: Size.infinite,
            painter: _getPainter(),
          );
        },
      ),
    );
  }

  CustomPainter _getPainter() {
    final primary = widget.primaryColor ?? DashColors.electricBlue;
    final secondary = widget.secondaryColor ?? DashColors.purpleGlow;

    switch (widget.type) {
      case BackgroundType.neuralGrid:
        return _NeuralGridPainter(
          animation: _controller,
          primaryColor: primary,
          secondaryColor: secondary,
        );
      case BackgroundType.particles:
        return _ParticlesBackgroundPainter(
          animation: _controller,
          color: primary,
        );
      case BackgroundType.energyLines:
        return _EnergyLinesPainter(
          animation: _controller,
          primaryColor: primary,
          secondaryColor: secondary,
        );
      case BackgroundType.constellation:
        return _ConstellationPainter(
          animation: _controller,
          color: primary,
        );
      case BackgroundType.circuitPattern:
        return _CircuitPatternPainter(
          animation: _controller,
          color: primary,
        );
      case BackgroundType.holographic:
        return _HolographicPainter(
          animation: _controller,
          primaryColor: primary,
          secondaryColor: secondary,
        );
    }
  }
}

/// Neural Grid Background
class _NeuralGridPainter extends CustomPainter {
  final Animation<double> animation;
  final Color primaryColor;
  final Color secondaryColor;

  _NeuralGridPainter({
    required this.animation,
    required this.primaryColor,
    required this.secondaryColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final nodes = _generateNodes(size);
    final paint = Paint()
      ..color = primaryColor.withValues(alpha: 0.3)
      ..strokeWidth = 1;

    for (int i = 0; i < nodes.length; i++) {
      for (int j = i + 1; j < nodes.length; j++) {
        final dist = _distance(nodes[i], nodes[j]);
        if (dist < 150) {
          final opacity = (1 - dist / 150) * 0.3;
          paint.color = primaryColor.withValues(alpha: opacity);
          canvas.drawLine(nodes[i], nodes[j], paint);
        }
      }
    }

    final nodePaint = Paint()
      ..color = secondaryColor.withValues(alpha: 0.5)
      ..style = PaintingStyle.fill;

    for (final node in nodes) {
      final pulse = math.sin(animation.value * 2 * math.pi + node.dx * 0.01);
      canvas.drawCircle(node, 2 + pulse, nodePaint);
    }
  }

  List<Offset> _generateNodes(Size size) {
    final random = math.Random(42);
    final nodes = <Offset>[];
    for (double x = 0; x < size.width; x += 80) {
      for (double y = 0; y < size.height; y += 80) {
        nodes.add(Offset(
          x + (random.nextDouble() - 0.5) * 40,
          y + (random.nextDouble() - 0.5) * 40,
        ));
      }
    }
    return nodes;
  }

  double _distance(Offset a, Offset b) {
    return math.sqrt(math.pow(a.dx - b.dx, 2) + math.pow(a.dy - b.dy, 2));
  }

  @override
  bool shouldRepaint(_NeuralGridPainter old) => old.animation.value != animation.value;
}

/// Particles Background
class _ParticlesBackgroundPainter extends CustomPainter {
  final Animation<double> animation;
  final Color color;

  _ParticlesBackgroundPainter({required this.animation, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: 0.4)
      ..style = PaintingStyle.fill;

    for (int i = 0; i < 50; i++) {
      final x = (i * 137.5) % size.width;
      final y = (i * 73.3 + animation.value * 50) % size.height;
      final sv = 1 + math.sin(animation.value * 2 * math.pi + i * 0.5) * 1.5;
      paint.color = color.withValues(alpha: 0.2 + math.sin(animation.value * 2 * math.pi + i) * 0.2);
      canvas.drawCircle(Offset(x, y), sv, paint);
    }
  }

  @override
  bool shouldRepaint(_ParticlesBackgroundPainter old) => old.animation.value != animation.value;
}

/// Energy Lines Background
class _EnergyLinesPainter extends CustomPainter {
  final Animation<double> animation;
  final Color primaryColor;
  final Color secondaryColor;

  _EnergyLinesPainter({
    required this.animation,
    required this.primaryColor,
    required this.secondaryColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    for (int i = 0; i < 8; i++) {
      final y = size.height * (i / 8) + size.height * 0.1;
      final path = Path();
      path.moveTo(0, y);
      for (double x = 0; x <= size.width; x += 20) {
        final waveY = y + math.sin(x * 0.01 + animation.value * 2 * math.pi + i) * 30;
        path.lineTo(x, waveY);
      }
      paint.color = i % 2 == 0
          ? primaryColor.withValues(alpha: 0.3)
          : secondaryColor.withValues(alpha: 0.2);
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(_EnergyLinesPainter old) => old.animation.value != animation.value;
}

/// Constellation Background
class _ConstellationPainter extends CustomPainter {
  final Animation<double> animation;
  final Color color;

  _ConstellationPainter({required this.animation, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final stars = _generateStars(size);
    final linePaint = Paint()
      ..color = color.withValues(alpha: 0.15)
      ..strokeWidth = 0.5;
    final starPaint = Paint()
      ..color = color.withValues(alpha: 0.6)
      ..style = PaintingStyle.fill;

    for (int i = 0; i < stars.length; i++) {
      for (int j = i + 1; j < stars.length; j++) {
        if (_distance(stars[i], stars[j]) < 200) {
          canvas.drawLine(stars[i], stars[j], linePaint);
        }
      }
    }

    for (final star in stars) {
      final twinkle = math.sin(animation.value * 4 * math.pi + star.dx * 0.1);
      starPaint.color = color.withValues(alpha: 0.4 + twinkle * 0.2);
      canvas.drawCircle(star, 1.5 + twinkle * 0.5, starPaint);
    }
  }

  List<Offset> _generateStars(Size size) {
    final random = math.Random(123);
    return List.generate(30, (_) => Offset(
      random.nextDouble() * size.width,
      random.nextDouble() * size.height,
    ));
  }

  double _distance(Offset a, Offset b) =>
      math.sqrt(math.pow(a.dx - b.dx, 2) + math.pow(a.dy - b.dy, 2));

  @override
  bool shouldRepaint(_ConstellationPainter old) => old.animation.value != animation.value;
}

/// Circuit Pattern Background
class _CircuitPatternPainter extends CustomPainter {
  final Animation<double> animation;
  final Color color;

  _CircuitPatternPainter({required this.animation, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: 0.2)
      ..strokeWidth = 1;

    for (double x = 0; x < size.width; x += 60) {
      for (double y = 0; y < size.height; y += 60) {
        final lp = (animation.value + (x + y) / (size.width + size.height)) % 1.0;
        if (lp < 0.3) {
          canvas.drawLine(Offset(x, y), Offset(x + 42, y), paint);
        } else if (lp < 0.6) {
          canvas.drawLine(Offset(x + 42, y), Offset(x + 42, y + 42), paint);
        } else {
          canvas.drawLine(Offset(x + 42, y + 42), Offset(x + 60, y + 42), paint);
        }
      }
    }
  }

  @override
  bool shouldRepaint(_CircuitPatternPainter old) => old.animation.value != animation.value;
}

/// Holographic Background
class _HolographicPainter extends CustomPainter {
  final Animation<double> animation;
  final Color primaryColor;
  final Color secondaryColor;

  _HolographicPainter({
    required this.animation,
    required this.primaryColor,
    required this.secondaryColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        primaryColor.withValues(alpha: 0.1),
        secondaryColor.withValues(alpha: 0.05),
        primaryColor.withValues(alpha: 0.1),
      ],
      stops: const [0.0, 0.5, 1.0],
    );

    final rect = Rect.fromLTWH(0, 0, size.width, size.height);
    final paint = Paint()..shader = gradient.createShader(rect);
    canvas.drawRect(rect, paint);

    final scanY = animation.value * size.height;
    final scanPaint = Paint()
      ..color = primaryColor.withValues(alpha: 0.1)
      ..style = PaintingStyle.fill;
    canvas.drawRect(Rect.fromLTWH(0, scanY, size.width, 2), scanPaint);

    final gridPaint = Paint()
      ..color = primaryColor.withValues(alpha: 0.05)
      ..strokeWidth = 0.5;
    for (double x = 0; x < size.width; x += 40) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += 40) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
  }

  @override
  bool shouldRepaint(_HolographicPainter old) => old.animation.value != animation.value;
}

/// Gradient background with animated colors
class AnimatedGradientBackground extends StatefulWidget {
  final List<Color> colors;
  final Duration duration;
  final Alignment begin;
  final Alignment end;

  const AnimatedGradientBackground({
    super.key,
    required this.colors,
    this.duration = const Duration(seconds: 10),
    this.begin = Alignment.topLeft,
    this.end = Alignment.bottomRight,
  });

  @override
  State<AnimatedGradientBackground> createState() =>
      _AnimatedGradientBackgroundState();
}

class _AnimatedGradientBackgroundState
    extends State<AnimatedGradientBackground>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: widget.duration,
      vsync: this,
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: widget.colors,
              begin: widget.begin,
              end: widget.end,
              stops: List.generate(
                widget.colors.length,
                (i) => i / (widget.colors.length - 1),
              ),
              transform: _GradientRotation(
                _controller.value * 2 * math.pi,
              ),
            ),
          ),
        );
      },
    );
  }
}

class _GradientRotation extends GradientTransform {
  final double angle;
  _GradientRotation(this.angle);

  @override
  Matrix4? transform(Rect bounds, {TextDirection? textDirection}) {
    final center = bounds.center;
    return Matrix4.identity()
      ..translate(center.dx, center.dy)
      ..rotateZ(angle)
      ..translate(-center.dx, -center.dy);
  }
}
