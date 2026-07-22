import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dash_mobile/features/workspace/workspace_page.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('WorkspacePage', () {
    testWidgets('renders workspace header', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: WorkspacePage()),
        ),
      );

      expect(find.text('AI Workspace'), findsOneWidget);
      expect(find.text('Your intelligent productivity hub'), findsOneWidget);
    });

    testWidgets('has quick actions section', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: WorkspacePage()),
        ),
      );

      expect(find.text('Quick Actions'), findsOneWidget);
    });

    testWidgets('has smart suggestions section', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: WorkspacePage()),
        ),
      );

      // Scroll down to find the Smart Suggestions section
      await tester.scrollUntilVisible(
        find.text('Smart Suggestions'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();

      expect(find.text('Smart Suggestions'), findsOneWidget);
    });

    testWidgets('has recent activity section', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: WorkspacePage()),
        ),
      );

      // Scroll down to find Recent Activity section
      await tester.scrollUntilVisible(
        find.text('Recent Activity'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();

      expect(find.text('Recent Activity'), findsOneWidget);
    });

    testWidgets('shows suggestion chips', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: WorkspacePage()),
        ),
      );

      // Scroll down to find suggestion chips
      await tester.scrollUntilVisible(
        find.text('What do you know about me?'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();

      expect(find.text('Summarize my recent conversations'), findsOneWidget);
      expect(find.text('Help me organize my projects'), findsOneWidget);
      expect(find.text('What do you know about me?'), findsOneWidget);
    });
  });
}

