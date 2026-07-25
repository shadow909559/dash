import 'dart:ui';
import 'package:flutter/material.dart';
import 'dash_theme.dart';

/// Custom theme extensions for DASH chat components.
class ChatTheme extends ThemeExtension<ChatTheme> {
  const ChatTheme({
    required this.userBubbleColor,
    required this.assistantBubbleColor,
    required this.userBubbleTextColor,
    required this.assistantBubbleTextColor,
    required this.userAvatarColor,
    required this.assistantAvatarColor,
    required this.bubbleShadowColor,
    required this.codeBlockBackground,
    required this.streamingCursorColor,
    required this.connectionBarColor,
    required this.suggestionChipBackground,
  });

  final Color userBubbleColor;
  final Color assistantBubbleColor;
  final Color userBubbleTextColor;
  final Color assistantBubbleTextColor;
  final Color userAvatarColor;
  final Color assistantAvatarColor;
  final Color bubbleShadowColor;
  final Color codeBlockBackground;
  final Color streamingCursorColor;
  final Color connectionBarColor;
  final Color suggestionChipBackground;

  @override
  ThemeExtension<ChatTheme> copyWith({
    Color? userBubbleColor,
    Color? assistantBubbleColor,
    Color? userBubbleTextColor,
    Color? assistantBubbleTextColor,
    Color? userAvatarColor,
    Color? assistantAvatarColor,
    Color? bubbleShadowColor,
    Color? codeBlockBackground,
    Color? streamingCursorColor,
    Color? connectionBarColor,
    Color? suggestionChipBackground,
  }) {
    return ChatTheme(
      userBubbleColor: userBubbleColor ?? this.userBubbleColor,
      assistantBubbleColor: assistantBubbleColor ?? this.assistantBubbleColor,
      userBubbleTextColor: userBubbleTextColor ?? this.userBubbleTextColor,
      assistantBubbleTextColor:
          assistantBubbleTextColor ?? this.assistantBubbleTextColor,
      userAvatarColor: userAvatarColor ?? this.userAvatarColor,
      assistantAvatarColor: assistantAvatarColor ?? this.assistantAvatarColor,
      bubbleShadowColor: bubbleShadowColor ?? this.bubbleShadowColor,
      codeBlockBackground: codeBlockBackground ?? this.codeBlockBackground,
      streamingCursorColor: streamingCursorColor ?? this.streamingCursorColor,
      connectionBarColor: connectionBarColor ?? this.connectionBarColor,
      suggestionChipBackground:
          suggestionChipBackground ?? this.suggestionChipBackground,
    );
  }

  @override
  ThemeExtension<ChatTheme> lerp(
    covariant ThemeExtension<ChatTheme>? other,
    double t,
  ) {
    if (other is! ChatTheme) return this;
    return ChatTheme(
      userBubbleColor:
          Color.lerp(userBubbleColor, other.userBubbleColor, t)!,
      assistantBubbleColor:
          Color.lerp(assistantBubbleColor, other.assistantBubbleColor, t)!,
      userBubbleTextColor:
          Color.lerp(userBubbleTextColor, other.userBubbleTextColor, t)!,
      assistantBubbleTextColor:
          Color.lerp(assistantBubbleTextColor, other.assistantBubbleTextColor, t)!,
      userAvatarColor: Color.lerp(userAvatarColor, other.userAvatarColor, t)!,
      assistantAvatarColor:
          Color.lerp(assistantAvatarColor, other.assistantAvatarColor, t)!,
      bubbleShadowColor:
          Color.lerp(bubbleShadowColor, other.bubbleShadowColor, t)!,
      codeBlockBackground:
          Color.lerp(codeBlockBackground, other.codeBlockBackground, t)!,
      streamingCursorColor:
          Color.lerp(streamingCursorColor, other.streamingCursorColor, t)!,
      connectionBarColor:
          Color.lerp(connectionBarColor, other.connectionBarColor, t)!,
      suggestionChipBackground:
          Color.lerp(suggestionChipBackground, other.suggestionChipBackground, t)!,
    );
  }
}

/// Glassmorphism theme extension
class GlassTheme extends ThemeExtension<GlassTheme> {
  const GlassTheme({
    required this.glassColor,
    required this.glassBlur,
    required this.glassOpacity,
    required this.borderColor,
    required this.borderWidth,
  });

  final Color glassColor;
  final double glassBlur;
  final double glassOpacity;
  final Color borderColor;
  final double borderWidth;

  @override
  ThemeExtension<GlassTheme> copyWith({
    Color? glassColor,
    double? glassBlur,
    double? glassOpacity,
    Color? borderColor,
    double? borderWidth,
  }) {
    return GlassTheme(
      glassColor: glassColor ?? this.glassColor,
      glassBlur: glassBlur ?? this.glassBlur,
      glassOpacity: glassOpacity ?? this.glassOpacity,
      borderColor: borderColor ?? this.borderColor,
      borderWidth: borderWidth ?? this.borderWidth,
    );
  }

  @override
  ThemeExtension<GlassTheme> lerp(
    covariant ThemeExtension<GlassTheme>? other,
    double t,
  ) {
    if (other is! GlassTheme) return this;
    return GlassTheme(
      glassColor: Color.lerp(glassColor, other.glassColor, t)!,
      glassBlur: lerpDouble(glassBlur, other.glassBlur, t)!,
      glassOpacity: lerpDouble(glassOpacity, other.glassOpacity, t)!,
      borderColor: Color.lerp(borderColor, other.borderColor, t)!,
      borderWidth: lerpDouble(borderWidth, other.borderWidth, t)!,
    );
  }
}

/// Glow theme extension
class GlowTheme extends ThemeExtension<GlowTheme> {
  const GlowTheme({
    required this.primaryGlow,
    required this.secondaryGlow,
    required this.successGlow,
    required this.errorGlow,
    required this.glowIntensity,
  });

  final Color primaryGlow;
  final Color secondaryGlow;
  final Color successGlow;
  final Color errorGlow;
  final double glowIntensity;

  @override
  ThemeExtension<GlowTheme> copyWith({
    Color? primaryGlow,
    Color? secondaryGlow,
    Color? successGlow,
    Color? errorGlow,
    double? glowIntensity,
  }) {
    return GlowTheme(
      primaryGlow: primaryGlow ?? this.primaryGlow,
      secondaryGlow: secondaryGlow ?? this.secondaryGlow,
      successGlow: successGlow ?? this.successGlow,
      errorGlow: errorGlow ?? this.errorGlow,
      glowIntensity: glowIntensity ?? this.glowIntensity,
    );
  }

  @override
  ThemeExtension<GlowTheme> lerp(
    covariant ThemeExtension<GlowTheme>? other,
    double t,
  ) {
    if (other is! GlowTheme) return this;
    return GlowTheme(
      primaryGlow: Color.lerp(primaryGlow, other.primaryGlow, t)!,
      secondaryGlow: Color.lerp(secondaryGlow, other.secondaryGlow, t)!,
      successGlow: Color.lerp(successGlow, other.successGlow, t)!,
      errorGlow: Color.lerp(errorGlow, other.errorGlow, t)!,
      glowIntensity: lerpDouble(glowIntensity, other.glowIntensity, t)!,
    );
  }
}

abstract final class AppTheme {
  static ThemeData get dark => _buildDarkTheme();
  
  static ThemeData get light => _buildLightTheme();
  
  static ThemeData _buildDarkTheme() {
    final colorScheme = ColorScheme.dark(
      primary: DashColors.electricBlue,
      onPrimary: DashColors.pureWhite,
      primaryContainer: DashColors.arcReactorBlue.withValues(alpha: 0.2),
      onPrimaryContainer: DashColors.pureWhite,
      secondary: DashColors.purpleGlow,
      onSecondary: DashColors.pureWhite,
      secondaryContainer: DashColors.deepPurple.withValues(alpha: 0.2),
      onSecondaryContainer: DashColors.pureWhite,
      tertiary: DashColors.energyGreen,
      onTertiary: DashColors.pureWhite,
      tertiaryContainer: DashColors.successGreen.withValues(alpha: 0.2),
      onTertiaryContainer: DashColors.pureWhite,
      error: DashColors.errorRed,
      onError: DashColors.pureWhite,
      errorContainer: DashColors.criticalRed.withValues(alpha: 0.2),
      onErrorContainer: DashColors.pureWhite,
      surface: DashColors.carbonBlack,
      onSurface: DashColors.softWhite,
      surfaceContainerHighest: DashColors.charcoal,
      outline: DashColors.textGray,
      outlineVariant: DashColors.textDim,
      scrim: Colors.black.withValues(alpha: 0.5),
    );

    final chatTheme = ChatTheme(
      userBubbleColor: DashColors.electricBlue.withValues(alpha: 0.2),
      assistantBubbleColor: DashColors.glassFrost.withValues(alpha: 0.1),
      userBubbleTextColor: DashColors.pureWhite,
      assistantBubbleTextColor: DashColors.softWhite,
      userAvatarColor: DashColors.electricBlue,
      assistantAvatarColor: DashColors.purpleGlow,
      bubbleShadowColor: Colors.black.withValues(alpha: 0.3),
      codeBlockBackground: DashColors.darkGraphite,
      streamingCursorColor: DashColors.electricBlue,
      connectionBarColor: DashColors.electricBlue.withValues(alpha: 0.15),
      suggestionChipBackground: DashColors.glassFrost.withValues(alpha: 0.15),
    );

    final glassTheme = GlassTheme(
      glassColor: DashColors.glassFrost,
      glassBlur: 20.0,
      glassOpacity: 0.1,
      borderColor: Colors.white.withValues(alpha: 0.1),
      borderWidth: 1.0,
    );

    final glowTheme = GlowTheme(
      primaryGlow: DashColors.electricBlue,
      secondaryGlow: DashColors.purpleGlow,
      successGlow: DashColors.energyGreen,
      errorGlow: DashColors.errorRed,
      glowIntensity: 0.4,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      extensions: [chatTheme, glassTheme, glowTheme],
      scaffoldBackgroundColor: DashColors.carbonBlack,
      
      // Typography
      textTheme: TextTheme(
        displayLarge: DashTypography.displayLarge.copyWith(color: DashColors.pureWhite),
        displayMedium: DashTypography.displayMedium.copyWith(color: DashColors.pureWhite),
        displaySmall: DashTypography.displaySmall.copyWith(color: DashColors.pureWhite),
        headlineLarge: DashTypography.headlineLarge.copyWith(color: DashColors.pureWhite),
        headlineMedium: DashTypography.headlineMedium.copyWith(color: DashColors.pureWhite),
        headlineSmall: DashTypography.headlineSmall.copyWith(color: DashColors.pureWhite),
        titleLarge: DashTypography.titleLarge.copyWith(color: DashColors.pureWhite),
        titleMedium: DashTypography.titleMedium.copyWith(color: DashColors.pureWhite),
        titleSmall: DashTypography.titleSmall.copyWith(color: DashColors.pureWhite),
        bodyLarge: DashTypography.bodyLarge.copyWith(color: DashColors.softWhite),
        bodyMedium: DashTypography.bodyMedium.copyWith(color: DashColors.softWhite),
        bodySmall: DashTypography.bodySmall.copyWith(color: DashColors.mutedWhite),
        labelLarge: DashTypography.labelLarge.copyWith(color: DashColors.pureWhite),
        labelMedium: DashTypography.labelMedium.copyWith(color: DashColors.mutedWhite),
        labelSmall: DashTypography.labelSmall.copyWith(color: DashColors.textGray),
      ),
      
      // App Bar
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: Colors.transparent,
        titleTextStyle: DashTypography.titleMedium.copyWith(
          color: DashColors.pureWhite,
        ),
        iconTheme: IconThemeData(
          color: DashColors.softWhite,
        ),
      ),
      
      // Cards
      cardTheme: CardThemeData(
        clipBehavior: Clip.antiAlias,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
        ),
        color: DashColors.glassFrost.withValues(alpha: 0.08),
        margin: const EdgeInsets.all(4),
      ),
      
      // Input
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
          borderSide: BorderSide.none,
        ),
        filled: true,
        fillColor: DashColors.glassFrost.withValues(alpha: 0.1),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        hintStyle: DashTypography.bodyMedium.copyWith(
          color: DashColors.textDim,
        ),
      ),
      
      // Buttons
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: DashColors.electricBlue,
          foregroundColor: DashColors.pureWhite,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: DashColors.electricBlue.withValues(alpha: 0.2),
          foregroundColor: DashColors.electricBlue,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: DashColors.electricBlue,
          side: BorderSide(
            color: DashColors.electricBlue.withValues(alpha: 0.5),
            width: 1.5,
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: DashColors.electricBlue,
          padding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 10,
          ),
          textStyle: DashTypography.labelMedium,
        ),
      ),
      
      // Navigation
      navigationBarTheme: NavigationBarThemeData(
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        elevation: 0,
        height: 70,
        backgroundColor: DashColors.glassFrost.withValues(alpha: 0.1),
        indicatorColor: DashColors.electricBlue.withValues(alpha: 0.2),
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return DashTypography.labelSmall.copyWith(
              color: DashColors.electricBlue,
            );
          }
          return DashTypography.labelSmall.copyWith(
            color: DashColors.textGray,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: DashColors.electricBlue,
            );
          }
          return const IconThemeData(
            color: DashColors.textGray,
          );
        }),
      ),
      
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: DashColors.glassFrost.withValues(alpha: 0.05),
        elevation: 0,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        labelType: NavigationRailLabelType.all,
        selectedLabelTextStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.electricBlue,
        ),
        unselectedLabelTextStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.textGray,
        ),
      ),
      
      // Other components
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: DashColors.charcoal,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        contentTextStyle: DashTypography.bodyMedium.copyWith(
          color: DashColors.pureWhite,
        ),
      ),
      
      dialogTheme: DialogThemeData(
        backgroundColor: DashColors.surfaceDark,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusXl),
        ),
        elevation: 0,
      ),
      
      dividerTheme: DividerThemeData(
        color: DashColors.textDim.withValues(alpha: 0.3),
        thickness: 0.5,
        space: 1,
      ),
      
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 8,
        ),
      ),
      
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: DashColors.surfaceDark,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(DashSpacing.radiusXxl),
          ),
        ),
        elevation: 0,
      ),
      
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
        ),
        backgroundColor: DashColors.glassFrost.withValues(alpha: 0.1),
        labelStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.softWhite,
        ),
      ),
      
      // Icons
      iconTheme: const IconThemeData(
        color: DashColors.softWhite,
      ),
      
      // Scrollbar
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.all(
          DashColors.electricBlue.withValues(alpha: 0.5),
        ),
        trackColor: WidgetStateProperty.all(
          DashColors.textDim.withValues(alpha: 0.2),
        ),
        thickness: WidgetStateProperty.all(6),
        radius: const Radius.circular(3),
        crossAxisMargin: 4,
        mainAxisMargin: 4,
      ),
    );
  }
  
  static ThemeData _buildLightTheme() {
    final colorScheme = ColorScheme.light(
      primary: DashColors.arcReactorBlue,
      onPrimary: DashColors.pureWhite,
      primaryContainer: DashColors.skyBlue.withValues(alpha: 0.15),
      onPrimaryContainer: DashColors.carbonBlack,
      secondary: DashColors.deepPurple,
      onSecondary: DashColors.pureWhite,
      secondaryContainer: DashColors.purpleGlow.withValues(alpha: 0.15),
      onSecondaryContainer: DashColors.carbonBlack,
      tertiary: DashColors.successGreen,
      onTertiary: DashColors.pureWhite,
      tertiaryContainer: DashColors.energyGreen.withValues(alpha: 0.15),
      onTertiaryContainer: DashColors.carbonBlack,
      error: DashColors.criticalRed,
      onError: DashColors.pureWhite,
      errorContainer: DashColors.errorRed.withValues(alpha: 0.15),
      onErrorContainer: DashColors.carbonBlack,
      surface: DashColors.softWhite,
      onSurface: DashColors.carbonBlack,
      surfaceContainerHighest: DashColors.mutedWhite.withValues(alpha: 0.5),
      outline: DashColors.textDim,
      outlineVariant: DashColors.textGray,
      scrim: Colors.black.withValues(alpha: 0.3),
    );

    final chatTheme = ChatTheme(
      userBubbleColor: DashColors.arcReactorBlue,
      assistantBubbleColor: DashColors.mutedWhite.withValues(alpha: 0.5),
      userBubbleTextColor: DashColors.pureWhite,
      assistantBubbleTextColor: DashColors.carbonBlack,
      userAvatarColor: DashColors.arcReactorBlue,
      assistantAvatarColor: DashColors.deepPurple,
      bubbleShadowColor: Colors.black.withValues(alpha: 0.08),
      codeBlockBackground: DashColors.darkGraphite,
      streamingCursorColor: DashColors.arcReactorBlue,
      connectionBarColor: DashColors.arcReactorBlue.withValues(alpha: 0.1),
      suggestionChipBackground: DashColors.mutedWhite.withValues(alpha: 0.5),
    );

    final glassTheme = GlassTheme(
      glassColor: DashColors.carbonBlack,
      glassBlur: 20.0,
      glassOpacity: 0.05,
      borderColor: DashColors.carbonBlack.withValues(alpha: 0.1),
      borderWidth: 1.0,
    );

    final glowTheme = GlowTheme(
      primaryGlow: DashColors.arcReactorBlue,
      secondaryGlow: DashColors.deepPurple,
      successGlow: DashColors.successGreen,
      errorGlow: DashColors.criticalRed,
      glowIntensity: 0.3,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      extensions: [chatTheme, glassTheme, glowTheme],
      scaffoldBackgroundColor: DashColors.softWhite,
      
      textTheme: TextTheme(
        displayLarge: DashTypography.displayLarge.copyWith(color: DashColors.carbonBlack),
        displayMedium: DashTypography.displayMedium.copyWith(color: DashColors.carbonBlack),
        displaySmall: DashTypography.displaySmall.copyWith(color: DashColors.carbonBlack),
        headlineLarge: DashTypography.headlineLarge.copyWith(color: DashColors.carbonBlack),
        headlineMedium: DashTypography.headlineMedium.copyWith(color: DashColors.carbonBlack),
        headlineSmall: DashTypography.headlineSmall.copyWith(color: DashColors.carbonBlack),
        titleLarge: DashTypography.titleLarge.copyWith(color: DashColors.carbonBlack),
        titleMedium: DashTypography.titleMedium.copyWith(color: DashColors.carbonBlack),
        titleSmall: DashTypography.titleSmall.copyWith(color: DashColors.carbonBlack),
        bodyLarge: DashTypography.bodyLarge.copyWith(color: DashColors.charcoal),
        bodyMedium: DashTypography.bodyMedium.copyWith(color: DashColors.charcoal),
        bodySmall: DashTypography.bodySmall.copyWith(color: DashColors.textDim),
        labelLarge: DashTypography.labelLarge.copyWith(color: DashColors.carbonBlack),
        labelMedium: DashTypography.labelMedium.copyWith(color: DashColors.textDim),
        labelSmall: DashTypography.labelSmall.copyWith(color: DashColors.textGray),
      ),
      
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        backgroundColor: Colors.transparent,
        titleTextStyle: DashTypography.titleMedium.copyWith(
          color: DashColors.carbonBlack,
        ),
        iconTheme: const IconThemeData(
          color: DashColors.charcoal,
        ),
      ),
      
      cardTheme: CardThemeData(
        clipBehavior: Clip.antiAlias,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
        ),
        color: DashColors.pureWhite,
        margin: const EdgeInsets.all(4),
      ),
      
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
          borderSide: BorderSide.none,
        ),
        filled: true,
        fillColor: DashColors.mutedWhite.withValues(alpha: 0.5),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        hintStyle: DashTypography.bodyMedium.copyWith(
          color: DashColors.textGray,
        ),
      ),
      
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: DashColors.arcReactorBlue,
          foregroundColor: DashColors.pureWhite,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: DashColors.skyBlue.withValues(alpha: 0.2),
          foregroundColor: DashColors.arcReactorBlue,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: DashColors.arcReactorBlue,
          side: BorderSide(
            color: DashColors.arcReactorBlue.withValues(alpha: 0.5),
            width: 1.5,
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 14,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
          ),
          textStyle: DashTypography.labelLarge,
        ),
      ),
      
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: DashColors.arcReactorBlue,
          padding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 10,
          ),
          textStyle: DashTypography.labelMedium,
        ),
      ),
      
      navigationBarTheme: NavigationBarThemeData(
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        elevation: 2,
        height: 70,
        backgroundColor: DashColors.pureWhite,
        indicatorColor: DashColors.skyBlue.withValues(alpha: 0.15),
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return DashTypography.labelSmall.copyWith(
              color: DashColors.arcReactorBlue,
            );
          }
          return DashTypography.labelSmall.copyWith(
            color: DashColors.textGray,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: DashColors.arcReactorBlue,
            );
          }
          return const IconThemeData(
            color: DashColors.textGray,
          );
        }),
      ),
      
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: DashColors.pureWhite,
        elevation: 2,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        labelType: NavigationRailLabelType.all,
        selectedLabelTextStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.arcReactorBlue,
        ),
        unselectedLabelTextStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.textGray,
        ),
      ),
      
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: DashColors.charcoal,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        contentTextStyle: DashTypography.bodyMedium.copyWith(
          color: DashColors.pureWhite,
        ),
      ),
      
      dialogTheme: DialogThemeData(
        backgroundColor: DashColors.pureWhite,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusXl),
        ),
        elevation: 8,
      ),
      
      dividerTheme: DividerThemeData(
        color: DashColors.textDim.withValues(alpha: 0.3),
        thickness: 0.5,
        space: 1,
      ),
      
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusMd),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 8,
        ),
      ),
      
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: DashColors.pureWhite,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(DashSpacing.radiusXxl),
          ),
        ),
        elevation: 16,
      ),
      
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
        ),
        backgroundColor: DashColors.mutedWhite.withValues(alpha: 0.5),
        labelStyle: DashTypography.labelSmall.copyWith(
          color: DashColors.charcoal,
        ),
      ),
      
      iconTheme: const IconThemeData(
        color: DashColors.charcoal,
      ),
      
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.all(
          DashColors.arcReactorBlue.withValues(alpha: 0.5),
        ),
        trackColor: WidgetStateProperty.all(
          DashColors.textGray.withValues(alpha: 0.2),
        ),
        thickness: WidgetStateProperty.all(6),
        radius: const Radius.circular(3),
        crossAxisMargin: 4,
        mainAxisMargin: 4,
      ),
    );
  }
}
