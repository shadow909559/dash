import 'package:dash_mobile/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders splash scaffold', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: DashApp()));

    // Avoid pumpAndSettle: Splash checks auth and uses async work that can keep
    // the widget tree busy (timers/network), causing pumpAndSettle to time out.
    await tester.pump();

    // Verify the splash screen is present.
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.byType(Icon), findsOneWidget);
  });

}

