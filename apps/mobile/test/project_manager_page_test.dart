import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dash_mobile/features/projects/project_manager_page.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ProjectManagerPage', () {
    testWidgets('renders empty state with message', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: ProjectManagerPage()),
        ),
      );

      expect(find.text('Projects'), findsOneWidget);
      expect(find.text('No projects yet'), findsOneWidget);
      expect(find.text('Create a project to organize your work'), findsOneWidget);
      expect(find.text('Create Project'), findsOneWidget);
    });

    testWidgets('opens create project dialog', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: ProjectManagerPage()),
        ),
      );

      // Tap create project button
      await tester.tap(find.text('Create Project'));
      await tester.pumpAndSettle();

      // Verify dialog appears
      expect(find.text('Create Project'), findsNWidgets(2)); // title + button
      expect(find.text('Project name'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    });

    testWidgets('can create a project from dialog', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: ProjectManagerPage()),
        ),
      );

      // Open create dialog
      await tester.tap(find.text('Create Project'));
      await tester.pumpAndSettle();

      // Enter project name
      await tester.enterText(find.byType(TextField).first, 'Test Project');
      await tester.tap(find.text('Create'));
      await tester.pumpAndSettle();

      // Project now appears in the list
      expect(find.text('Test Project'), findsOneWidget);
    });

    testWidgets('cancel closes dialog without creating', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: ProjectManagerPage()),
        ),
      );

      // Open dialog
      await tester.tap(find.text('Create Project'));
      await tester.pumpAndSettle();

      // Cancel
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog should be gone, empty state still exists
      expect(find.text('No projects yet'), findsOneWidget);
    });

    testWidgets('has header with new button', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: ProjectManagerPage()),
        ),
      );

      expect(find.text('New'), findsOneWidget);
      expect(find.byIcon(Icons.folder_outlined), findsOneWidget);
    });
  });
}

