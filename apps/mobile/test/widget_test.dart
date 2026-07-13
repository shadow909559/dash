import 'package:flutter_test/flutter_test.dart';
import 'package:dash_mobile/main.dart';

void main() {
  testWidgets('renders app title', (tester) async {
    await tester.pumpWidget(const DashApp());
    expect(find.text('DASH'), findsOneWidget);
    expect(find.text('Foundation milestone — v0.1.0'), findsOneWidget);
  });
}
