import 'package:flutter/material.dart';

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

abstract final class AppTheme {
  static const Color _seedColor = Color(0xFF38BDF8);

  static ThemeData get light {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: Brightness.light,
    );

    return _themeFromScheme(colorScheme);
  }

  static ThemeData get dark {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: Brightness.dark,
    );

    return _themeFromScheme(colorScheme);
  }

  static ThemeData _themeFromScheme(ColorScheme colorScheme) {
    final isDark = colorScheme.brightness == Brightness.dark;

    final chatTheme = ChatTheme(
      userBubbleColor: isDark
          ? colorScheme.primaryContainer
          : colorScheme.primaryContainer,
      assistantBubbleColor: isDark
          ? colorScheme.surfaceContainerHighest
          : const Color(0xFFF0F4F8),
      userBubbleTextColor: colorScheme.onPrimaryContainer,
      assistantBubbleTextColor: colorScheme.onSurface,
      userAvatarColor: colorScheme.primaryContainer,
      assistantAvatarColor: colorScheme.secondaryContainer,
      bubbleShadowColor: isDark
          ? Colors.black.withValues(alpha: 0.2)
          : Colors.black.withValues(alpha: 0.06),
      codeBlockBackground: isDark
          ? const Color(0xFF1E1E2E)
          : const Color(0xFFF5F5F5),
      streamingCursorColor: colorScheme.primary,
      connectionBarColor: isDark
          ? colorScheme.primary.withValues(alpha: 0.15)
          : colorScheme.primary.withValues(alpha: 0.08),
      suggestionChipBackground: isDark
          ? colorScheme.surfaceContainerHigh
          : colorScheme.surfaceContainerLow,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      extensions: [chatTheme],
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        titleTextStyle: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: colorScheme.onSurface,
        ),
      ),
      cardTheme: CardThemeData(
        clipBehavior: Clip.antiAlias,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        color: colorScheme.surface,
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        filled: true,
        fillColor: colorScheme.surfaceContainerHighest,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 12,
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        elevation: 2,
        height: 65,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        labelType: NavigationRailLabelType.all,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.outlineVariant,
        thickness: 0.5,
        space: 1,
      ),
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(20),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
    );
  }
}

