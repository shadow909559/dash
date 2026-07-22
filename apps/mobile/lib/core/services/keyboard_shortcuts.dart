import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

/// Provides keyboard shortcut handling for the DASH app.
class KeyboardShortcuts extends StatelessWidget {
  final Widget child;

  const KeyboardShortcuts({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return CallbackShortcuts(
      bindings: <ShortcutActivator, VoidCallback>{
        // Ctrl+N: New chat
        const SingleActivator(LogicalKeyboardKey.keyN, control: true): () {
          context.go('/chat');
        },

        // Ctrl+K: Search conversations
        const SingleActivator(LogicalKeyboardKey.keyK, control: true): () {
          // Trigger search - will be implemented in search page
          context.go('/chat');
        },

        // Ctrl+Shift+M: Memory browser
        const SingleActivator(LogicalKeyboardKey.keyM,
            control: true, shift: true): () {
          context.go('/memory');
        },

        // Ctrl+, : Settings
        const SingleActivator(LogicalKeyboardKey.keyB, control: true): () {
          context.go('/settings');
        },

        // Ctrl+Shift+D: Dashboard
        const SingleActivator(LogicalKeyboardKey.keyD,
            control: true, shift: true): () {
          context.go('/dashboard');
        },

        // Escape: go back
        const SingleActivator(LogicalKeyboardKey.escape): () {
          if (Navigator.of(context).canPop()) {
            Navigator.of(context).pop();
          }
        },
      },
      child: Focus(
        autofocus: true,
        child: child,
      ),
    );
  }
}

