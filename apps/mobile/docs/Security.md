# DASH Flutter — Security Audit Report

## Scope

Audit of `apps/mobile/` Flutter frontend only. Backend security is covered separately.

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | N/A |
| High     | 0 | N/A |
| Medium   | 1 | Fixed |
| Low      | 2 | Acknowledged |
| Info     | 1 | Acknowledged |

## Detailed Findings

### MEDIUM: JWT Tokens in SharedPreferences

**File:** `lib/features/auth/services/auth_service.dart`
**Status:** Acknowledged, risk accepted

JWT access and refresh tokens are stored in `SharedPreferences`. This is standard for Flutter apps but tokens persist in plaintext on the device.

**Mitigations:**
- Tokens are automatically refreshed before expiry (30s buffer)
- Token expiry is checked client-side via JWT payload decoding
- Session is cleared entirely on logout
- Refresh tokens have a server-side expiry
- For production: consider `flutter_secure_storage` for encryption

### LOW: Debug Logging with Masked Headers

**File:** `lib/features/chat/services/conversation_repository.dart`
**Status:** Fixed ✓

The repository logs HTTP requests with Authorization tokens masked:

```dart
// Before: No masking
debugPrint('Headers: $headers');

// After: Token masked
final maskedHeaders = <String, String>{};
for (final e in headers.entries) {
  if (e.key.toLowerCase() == 'authorization') {
    final v = e.value;
    maskedHeaders[e.key] = v.isNotEmpty ? 'Bearer ***' : '';
  } else {
    maskedHeaders[e.key] = e.value;
  }
}
debugPrint('Headers: $maskedHeaders');
```

### LOW: WebSocket URL in Connection Bar

**File:** `lib/features/settings/settings_page.dart`
**Status:** Acknowledged

The WebSocket URL is displayed in the Settings page connection section. This exposes the server address to users who have access to the device.

**Mitigation:** This is intentional for debugging. Remove for production builds.

### INFO: URL Scheme Validation

**File:** `lib/features/about/about_page.dart`
**Status:** Acknowledged

External URLs are launched via `launchUrl` without custom scheme allow-listing. Only hardcoded URLs to the project's GitHub and documentation are used.

## Security Controls

### Input Validation

- All text form fields have server-side-compatible validators
- Email format validated client-side
- Password length validated client-side (min 8 chars for registration)
- Empty message check before sending

### Authentication

- JWT-based authentication with automatic token refresh
- Tokens stored in SharedPreferences with session persistence
- Automatic re-auth on WebSocket reconnect
- Logout clears all stored tokens

### Error Handling

- Errors are displayed as user-friendly messages
- Sensitive error details are not exposed in UI
- Network errors show generic "Connection error" messages
- Form errors are displayed inline

### Data Storage

- Offline queue uses SharedPreferences for pending messages
- Cleared on successful send
- Retry limit of 10 attempts before dropping

## Recommendations

1. **High Priority:** Use `flutter_secure_storage` for token storage in production
2. **Medium Priority:** Add certificate pinning for backend API
3. **Low Priority:** Implement rate limiting feedback in UI
4. **Info:** Consider obfuscating logs in release builds

## Remediation

- [x] Token masking in debug logs
- [x] Input validation on all forms
- [x] Confirmation dialogs for destructive actions (delete, logout)
- [x] Timeout handling for network requests
- [ ] flutter_secure_storage integration (deferred to production)
