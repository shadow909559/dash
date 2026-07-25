import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Premium futuristic color palette
/// Apple Vision Pro, and Tesla UI.
class DashColors {
  // Base Colors
  static const Color carbonBlack = Color(0xFF0A0A0F);
  static const Color deepNavy = Color(0xFF0D1117);
  static const Color darkGraphite = Color(0xFF161B22);
  static const Color charcoal = Color(0xFF21262D);
  static const Color surfaceDark = Color(0xFF1C2128);
  
  // Accent Colors - Electric Blue / Arc Reactor
  static const Color electricBlue = Color(0xFF00D4FF);
  static const Color arcReactorBlue = Color(0xFF00A8FF);
  static const Color neonCyan = Color(0xFF00FFFF);
  static const Color skyBlue = Color(0xFF38BDF8);
  
  // Purple Glow
  static const Color purpleGlow = Color(0xFF8B5CF6);
  static const Color violetAccent = Color(0xFFA78BFA);
  static const Color deepPurple = Color(0xFF6366F1);
  
  // Energy Colors
  static const Color energyGreen = Color(0xFF10B981);
  static const Color successGreen = Color(0xFF22C55E);
  static const Color warningAmber = Color(0xFFF59E0B);
  static const Color errorRed = Color(0xFFEF4444);
  static const Color criticalRed = Color(0xFFDC2626);
  
  // Glass & Frost
  static const Color glassFrost = Color(0x1AFFFFFF);
  static const Color glassDark = Color(0x0DFFFFFF);
  static const Color glassLight = Color(0x33FFFFFF);
  
  // Text Colors
  static const Color pureWhite = Color(0xFFFFFFFF);
  static const Color softWhite = Color(0xFFF0F4F8);
  static const Color mutedWhite = Color(0xFFB4B9C2);
  static const Color textGray = Color(0xFF8B949E);
  static const Color textDim = Color(0xFF6E7681);
  
  // Gradient Colors
  static const List<Color> blueGradient = [
    Color(0xFF00D4FF),
    Color(0xFF00A8FF),
    Color(0xFF38BDF8),
  ];
  
  static const List<Color> purpleGradient = [
    Color(0xFF8B5CF6),
    Color(0xFF6366F1),
    Color(0xFFA78BFA),
  ];
  
  static const List<Color> energyGradient = [
    Color(0xFF00D4FF),
    Color(0xFF10B981),
    Color(0xFF8B5CF6),
  ];
  
  static const List<Color> darkGradient = [
    Color(0xFF0A0A0F),
    Color(0xFF0D1117),
    Color(0xFF161B22),
  ];
  
  // Glow Effects
  static const Color blueGlow = Color(0x4000D4FF);
  static const Color purpleGlowEffect = Color(0x408B5CF6);
  static const Color greenGlow = Color(0x4010B981);
  static const Color redGlow = Color(0x40EF4444);
}

/// Premium typography system using Google Fonts
class DashTypography {
  static const String fontFamily = 'Inter';
  
  // Display
  static TextStyle get displayLarge => GoogleFonts.inter(
    fontSize: 57,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.5,
    height: 1.1,
  );
  
  static TextStyle get displayMedium => GoogleFonts.inter(
    fontSize: 45,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.25,
    height: 1.2,
  );
  
  static TextStyle get displaySmall => GoogleFonts.inter(
    fontSize: 36,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.3,
  );
  
  // Headline
  static TextStyle get headlineLarge => GoogleFonts.inter(
    fontSize: 32,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.3,
  );
  
  static TextStyle get headlineMedium => GoogleFonts.inter(
    fontSize: 28,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.3,
  );
  
  static TextStyle get headlineSmall => GoogleFonts.inter(
    fontSize: 24,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.4,
  );
  
  // Title
  static TextStyle get titleLarge => GoogleFonts.inter(
    fontSize: 22,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.4,
  );
  
  static TextStyle get titleMedium => GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.15,
    height: 1.5,
  );
  
  static TextStyle get titleSmall => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    height: 1.5,
  );
  
  // Body
  static TextStyle get bodyLarge => GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.5,
    height: 1.5,
  );
  
  static TextStyle get bodyMedium => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.25,
    height: 1.5,
  );
  
  static TextStyle get bodySmall => GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.4,
    height: 1.5,
  );
  
  // Label
  static TextStyle get labelLarge => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    height: 1.4,
  );
  
  static TextStyle get labelMedium => GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
    height: 1.4,
  );
  
  static TextStyle get labelSmall => GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
    height: 1.4,
  );
  
  // Monospace for code
  static TextStyle get code => GoogleFonts.jetBrainsMono(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    letterSpacing: 0,
    height: 1.5,
  );
  
  static TextStyle get codeSmall => GoogleFonts.jetBrainsMono(
    fontSize: 11,
    fontWeight: FontWeight.w400,
    letterSpacing: 0,
    height: 1.4,
  );
}

/// Spacing system following 8pt grid
class DashSpacing {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 16.0;
  static const double lg = 24.0;
  static const double xl = 32.0;
  static const double xxl = 48.0;
  static const double xxxl = 64.0;
  
  // Border radius
  static const double radiusSm = 8.0;
  static const double radiusMd = 12.0;
  static const double radiusLg = 16.0;
  static const double radiusXl = 20.0;
  static const double radiusXxl = 24.0;
  static const double radiusFull = 999.0;
}

/// Elevation and shadow system
class DashElevation {
  static const double none = 0.0;
  static const double sm = 2.0;
  static const double md = 4.0;
  static const double lg = 8.0;
  static const double xl = 16.0;
  static const double xxl = 24.0;
  
  static List<BoxShadow> get shadowSm => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.1),
      blurRadius: 4,
      offset: const Offset(0, 2),
    ),
  ];
  
  static List<BoxShadow> get shadowMd => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.15),
      blurRadius: 8,
      offset: const Offset(0, 4),
    ),
  ];
  
  static List<BoxShadow> get shadowLg => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.2),
      blurRadius: 16,
      offset: const Offset(0, 8),
    ),
  ];
  
  static List<BoxShadow> get shadowXl => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.25),
      blurRadius: 24,
      offset: const Offset(0, 12),
    ),
  ];
  
  // Glow effects
  static List<BoxShadow> blueGlow({double opacity = 0.4}) => [
    BoxShadow(
      color: DashColors.electricBlue.withValues(alpha: opacity),
      blurRadius: 20,
      offset: const Offset(0, 0),
      spreadRadius: 0,
    ),
  ];
  
  static List<BoxShadow> purpleGlow({double opacity = 0.4}) => [
    BoxShadow(
      color: DashColors.purpleGlow.withValues(alpha: opacity),
      blurRadius: 20,
      offset: const Offset(0, 0),
      spreadRadius: 0,
    ),
  ];
  
  static List<BoxShadow> greenGlow({double opacity = 0.4}) => [
    BoxShadow(
      color: DashColors.energyGreen.withValues(alpha: opacity),
      blurRadius: 20,
      offset: const Offset(0, 0),
      spreadRadius: 0,
    ),
  ];
  
  static List<BoxShadow> redGlow({double opacity = 0.4}) => [
    BoxShadow(
      color: DashColors.errorRed.withValues(alpha: opacity),
      blurRadius: 20,
      offset: const Offset(0, 0),
      spreadRadius: 0,
    ),
  ];
}

/// Glassmorphism utilities
class DashGlass {
  static BoxDecoration glassCard({
    Color? color,
    double blur = 20,
    double opacity = 0.1,
    double borderRadius = DashSpacing.radiusLg,
    Border? border,
  }) {
    return BoxDecoration(
      color: (color ?? DashColors.glassFrost).withValues(alpha: opacity),
      borderRadius: BorderRadius.circular(borderRadius),
      border: border ?? Border.all(
        color: Colors.white.withValues(alpha: 0.1),
        width: 1,
      ),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.1),
          blurRadius: blur,
          offset: const Offset(0, 4),
        ),
      ],
    );
  }
  
  static BoxDecoration glassPanel({
    Color? color,
    double blur = 30,
    double opacity = 0.15,
    double borderRadius = DashSpacing.radiusXl,
  }) {
    return BoxDecoration(
      color: (color ?? DashColors.glassFrost).withValues(alpha: opacity),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(
        color: Colors.white.withValues(alpha: 0.15),
        width: 1.5,
      ),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.15),
          blurRadius: blur,
          offset: const Offset(0, 8),
        ),
      ],
    );
  }
  
  static BoxDecoration glassButton({
    Color? color,
    double blur = 15,
    double opacity = 0.2,
    double borderRadius = DashSpacing.radiusMd,
  }) {
    return BoxDecoration(
      color: (color ?? DashColors.glassFrost).withValues(alpha: opacity),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(
        color: Colors.white.withValues(alpha: 0.2),
        width: 1,
      ),
    );
  }
}

/// Gradient utilities
class DashGradients {
  static LinearGradient get blue => const LinearGradient(
    colors: DashColors.blueGradient,
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  
  static LinearGradient get purple => const LinearGradient(
    colors: DashColors.purpleGradient,
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  
  static LinearGradient get energy => const LinearGradient(
    colors: DashColors.energyGradient,
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  
  static LinearGradient get dark => const LinearGradient(
    colors: DashColors.darkGradient,
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  
  static LinearGradient radialBlue({
    Alignment center = Alignment.center,
    double radius = 1.0,
  }) {
    return LinearGradient(
      colors: DashColors.blueGradient,
      begin: center,
      end: Alignment(center.x, center.y + radius),
    );
  }
  
  static LinearGradient radialPurple({
    Alignment center = Alignment.center,
    double radius = 1.0,
  }) {
    return LinearGradient(
      colors: DashColors.purpleGradient,
      begin: center,
      end: Alignment(center.x, center.y + radius),
    );
  }
  
  static LinearGradient animated({
    required List<Color> colors,
    Alignment begin = Alignment.topLeft,
    Alignment end = Alignment.bottomRight,
  }) {
    return LinearGradient(
      colors: colors,
      begin: begin,
      end: end,
    );
  }
}

/// Animation durations
class DashDuration {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 300);
  static const Duration slow = Duration(milliseconds: 500);
  static const Duration slower = Duration(milliseconds: 700);
  static const Duration slowest = Duration(milliseconds: 1000);
  
  // Specific animations
  static const Duration pulse = Duration(milliseconds: 1500);
  static const Duration breathe = Duration(milliseconds: 3000);
  static const Duration rotate = Duration(milliseconds: 20000);
  static const Duration glow = Duration(milliseconds: 1000);
}

/// Animation curves
class DashCurves {
  static const Curve easeInOut = Curves.easeInOut;
  static const Curve easeOut = Curves.easeOut;
  static const Curve easeIn = Curves.easeIn;
  static const Curve bounceIn = Curves.bounceIn;
  static const Curve bounceOut = Curves.bounceOut;
  static const Curve elasticOut = Curves.elasticOut;
  static const Curve fastOutSlowIn = Curves.fastOutSlowIn;
}
