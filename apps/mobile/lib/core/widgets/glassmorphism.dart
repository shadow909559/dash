import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/dash_theme.dart';
import '../theme/app_theme.dart';

/// Premium Glassmorphism Card Widget
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry margin;
  final double? width;
  final double? height;
  final double borderRadius;
  final double blur;
  final double opacity;
  final Color? borderColor;
  final double borderWidth;
  final VoidCallback? onTap;
  final List<BoxShadow>? boxShadow;
  final AlignmentGeometry? alignment;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin = EdgeInsets.zero,
    this.width,
    this.height,
    this.borderRadius = DashSpacing.radiusLg,
    this.blur = 20,
    this.opacity = 0.1,
    this.borderColor,
    this.borderWidth = 1,
    this.onTap,
    this.boxShadow,
    this.alignment,
  });

  @override
  Widget build(BuildContext context) {
    final glassTheme = Theme.of(context).extension<GlassTheme>();
    
    Widget card = Container(
      width: width,
      height: height,
      margin: margin,
      padding: padding,
      alignment: alignment,
      decoration: BoxDecoration(
        color: (glassTheme?.glassColor ?? DashColors.glassFrost)
            .withValues(alpha: glassTheme?.glassOpacity ?? opacity),
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(
          color: borderColor ?? 
              (glassTheme?.borderColor ?? Colors.white.withValues(alpha: 0.1)),
          width: borderWidth,
        ),
        boxShadow: boxShadow ??
            [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: blur,
                offset: const Offset(0, 4),
              ),
            ],
      ),
      child: child,
    );

    if (onTap != null) {
      card = InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(borderRadius),
        child: card,
      );
    }

    return card.animate().fadeIn(duration: DashDuration.normal);
  }
}

/// Premium Glassmorphism Panel Widget
class GlassPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry margin;
  final double? width;
  final double? height;
  final double borderRadius;
  final double blur;
  final double opacity;
  final VoidCallback? onTap;

  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(24),
    this.margin = const EdgeInsets.all(8),
    this.width,
    this.height,
    this.borderRadius = DashSpacing.radiusXl,
    this.blur = 30,
    this.opacity = 0.15,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: padding,
      margin: margin,
      width: width,
      height: height,
      borderRadius: borderRadius,
      blur: blur,
      opacity: opacity,
      borderWidth: 1.5,
      onTap: onTap,
      child: child,
    );
  }
}

/// Premium Glassmorphism Button Widget
class GlassButton extends StatelessWidget {
  final Widget child;
  final VoidCallback? onPressed;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final double blur;
  final double opacity;
  final Color? activeColor;
  final bool isSecondary;
  final double? width;
  final double? height;

  const GlassButton({
    super.key,
    required this.child,
    this.onPressed,
    this.padding = const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
    this.borderRadius = DashSpacing.radiusMd,
    this.blur = 15,
    this.opacity = 0.2,
    this.activeColor,
    this.isSecondary = false,
    this.width,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final activeColor = this.activeColor ?? 
        (isSecondary ? theme.colorScheme.secondary : theme.colorScheme.primary);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(borderRadius),
        child: Container(
          width: width,
          height: height,
          padding: padding,
          decoration: BoxDecoration(
            color: activeColor.withValues(alpha: opacity),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: activeColor.withValues(alpha: 0.3),
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: activeColor.withValues(alpha: 0.2),
                blurRadius: blur,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: child,
        ),
      ),
    );
  }
}

/// Glassmorphism Input Field
class GlassInput extends StatelessWidget {
  final String? hintText;
  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final int maxLines;
  final int? minLines;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? prefixIcon;
  final Widget? suffixIcon;
  final String? labelText;
  final EdgeInsetsGeometry padding;
  final FocusNode? focusNode;
  final String? Function(String?)? validator;
  final bool enabled;
  final TextInputAction? textInputAction;

  const GlassInput({
    super.key,
    this.hintText,
    this.controller,
    this.onChanged,
    this.onSubmitted,
    this.maxLines = 1,
    this.minLines,
    this.keyboardType,
    this.obscureText = false,
    this.prefixIcon,
    this.suffixIcon,
    this.labelText,
    this.padding = const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    this.focusNode,
    this.validator,
    this.enabled = true,
    this.textInputAction,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasValidator = validator != null;

    if (hasValidator && controller != null) {
      return FormField<String>(
        validator: validator,
        initialValue: controller?.text ?? "",
        builder: (field) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                decoration: BoxDecoration(
                  color: DashColors.glassFrost.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.1),
                    width: 1,
                  ),
                ),
                child: TextField(
                  controller: controller,
                  focusNode: focusNode,
                  onChanged: (value) {
                    field.didChange(value);
                    onChanged?.call(value);
                  },
                  onSubmitted: onSubmitted,
                  maxLines: maxLines,
                  minLines: minLines,
                  keyboardType: keyboardType,
                  obscureText: obscureText,
                  enabled: enabled,
                  textInputAction: textInputAction,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface,
                  ),
                  decoration: InputDecoration(
                    hintText: hintText,
                    labelText: labelText,
                    prefixIcon: prefixIcon,
                    suffixIcon: suffixIcon,
                    border: InputBorder.none,
                    contentPadding: padding,
                    hintStyle: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                    ),
                    labelStyle: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                ),
              ),
              if (field.hasError)
                Padding(
                  padding: const EdgeInsets.only(left: 12, top: 6),
                  child: Text(
                    field.errorText ?? '',
                    style: const TextStyle(color: DashColors.errorRed, fontSize: 11),
                  ),
                ),
            ],
          );
        },
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: DashColors.glassFrost.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(DashSpacing.radiusLg),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.1),
          width: 1,
        ),
      ),
      child: TextField(
        controller: controller,
        focusNode: focusNode,
        onChanged: onChanged,
        onSubmitted: onSubmitted,
        maxLines: maxLines,
        minLines: minLines,
        keyboardType: keyboardType,
        obscureText: obscureText,
        enabled: enabled,
        textInputAction: textInputAction,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurface,
        ),
        decoration: InputDecoration(
          hintText: hintText,
          labelText: labelText,
          prefixIcon: prefixIcon,
          suffixIcon: suffixIcon,
          border: InputBorder.none,
          contentPadding: padding,
          hintStyle: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          ),
          labelStyle: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}
