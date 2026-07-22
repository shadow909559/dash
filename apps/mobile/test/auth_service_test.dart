import 'package:flutter_test/flutter_test.dart';
import 'package:dash_mobile/features/auth/models/auth_user.dart';
import 'package:dash_mobile/features/auth/models/auth_token_response.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthUser', () {
    test('creates from JSON', () {
      final json = {
        'id': 'user_1',
        'email': 'test@example.com',
        'username': 'testuser',
        'is_active': true,
        'created_at': '2025-01-01T00:00:00.000Z',
      };

      final user = AuthUser.fromJson(json);
      expect(user.id, equals('user_1'));
      expect(user.email, equals('test@example.com'));
      expect(user.username, equals('testuser'));
      expect(user.isActive, isTrue);
    });

    test('toJson round-trip', () {
      final user = AuthUser(
        id: 'user_2',
        email: 'test@example.com',
        username: 'testuser',
        isActive: true,
        createdAt: DateTime(2025, 1, 1),
      );

      final json = user.toJson();
      final restored = AuthUser.fromJson(json);
      expect(restored.id, equals(user.id));
      expect(restored.email, equals(user.email));
      expect(restored.username, equals(user.username));
      expect(restored.isActive, equals(user.isActive));
    });
  });

  group('AuthTokenResponse', () {
    test('creates from JSON', () {
      final json = {
        'access_token': 'access_123',
        'refresh_token': 'refresh_456',
        'token_type': 'bearer',
        'expires_in': 3600,
        'user': {
          'id': 'user_1',
          'email': 'test@example.com',
          'username': 'testuser',
          'is_active': true,
          'created_at': '2025-01-01T00:00:00.000Z',
        },
      };

      final response = AuthTokenResponse.fromJson(json);
      expect(response.accessToken, equals('access_123'));
      expect(response.refreshToken, equals('refresh_456'));
      expect(response.tokenType, equals('bearer'));
      expect(response.expiresIn, equals(3600));
      expect(response.user.username, equals('testuser'));
    });

    test('uses default token_type when missing', () {
      final json = {
        'access_token': 'access_123',
        'refresh_token': 'refresh_456',
        'expires_in': 3600,
        'user': {
          'id': 'user_1',
          'email': 'test@example.com',
          'username': 'testuser',
          'is_active': true,
          'created_at': '2025-01-01T00:00:00.000Z',
        },
      };

      final response = AuthTokenResponse.fromJson(json);
      expect(response.tokenType, equals('bearer'));
    });
  });
}

