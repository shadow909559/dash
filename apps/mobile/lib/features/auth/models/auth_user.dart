/// Dart model matching the backend [UserRead] schema.
class AuthUser {
  final String id;
  final String email;
  final String username;
  final bool isActive;
  final DateTime createdAt;

  const AuthUser({
    required this.id,
    required this.email,
    required this.username,
    required this.isActive,
    required this.createdAt,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: json['id'] as String,
      email: json['email'] as String,
      username: json['username'] as String,
      isActive: json['is_active'] as bool,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'username': username,
      'is_active': isActive,
      'created_at': createdAt.toIso8601String(),
    };
  }
}