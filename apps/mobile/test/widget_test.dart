import 'package:dash_mobile/app.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders splash scaffold', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: DashApp()));
    await tester.pumpAndSettle();

    expect(find.text('DASH'), findsOneWidget);
    expect(find.text('Mobile assistant'), findsOneWidget);
    expect(find.text('Continue'), findsOneWidget);
  });
}
