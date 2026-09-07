# DASH Security Audit — Website, Backend, Desktop

## Date: 2026-09-08

---

## 1. API Keys & Secrets

| Target | Issue | Status | Action |
|--------|-------|--------|--------|
| Desktop `.env` in git | Real API keys (Groq, Gemini, Grok) tracked | **FIXED** | Removed from git, `.env.example` created |
| Backend `.env` | Contains real JWT secret, API keys | **OK** | `.gitignore` excludes it |
| Mobile `.env` | Contains real tokens | **OK** | Not tracked in git |
| Website frontend | No secrets found | **PASS** | All config via env vars |
| Desktop frontend | No `VITE_*` keys in source | **PASS** | Keys only in `.env` |

## 2. Route Protection

| Route | Auth Required | Status |
|-------|--------------|--------|
| `/auth/*` | Rate limited (10/min) | OK |
| `/ec2/*` (start/stop cloud) | **FIXED** — Added `get_current_user` | Fixed |
| `/ecosystem/dispatch` (run agents) | **FIXED** — Added `get_current_user` | Fixed |
| `/fine-tuning/*` (9 endpoints) | **FIXED** — Added `get_current_user` | Fixed |
| `/legal/*` (public docs) | None (intentional) | OK |
| All other routes | Auth required | OK |

## 3. Input Sanitization

| Check | Status | Detail |
|-------|--------|--------|
| SQL injection | **OK** | SQLAlchemy ORM throughout, no raw SQL |
| XSS in desktop | **OK** | No `dangerouslySetInnerHTML` found |
| XSS in website | **OK** | React escapes by default |
| Memory input sanitization | **FIXED** | Pydantic validators strip HTML/script tags |
| Filename sanitization | **FIXED** | Path traversal prevention on file uploads |

## 4. Rate Limiting

| Endpoint | Limit | Status |
|----------|-------|--------|
| Auth (login/register) | 10 req/min per IP | OK (existing) |
| WebSocket messages | 30 msg/min per user | OK (existing) |
| All API endpoints | 120 req/min per IP | **FIXED** (new) |

## 5. Security Headers

| Header | Value | Status |
|--------|-------|--------|
| X-Content-Type-Options | nosniff | **FIXED** |
| X-Frame-Options | DENY | **FIXED** |
| X-XSS-Protection | 1; mode=block | **FIXED** |
| Referrer-Policy | strict-origin-when-cross-origin | **FIXED** |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | **FIXED** |
| Strict-Transport-Security | max-age=31536000 (production only) | **FIXED** |
| Content-Security-Policy | default-src 'self'; script-src 'self' | **FIXED** |

## 6. CORS

| Check | Status | Detail |
|-------|--------|--------|
| Wildcard in production | **OK** | Blocked by existing sanity check |
| Development origins | OK | localhost:5173, 10.0.2.2:8000 |

## 7. File Uploads

| Check | Status | Detail |
|-------|--------|--------|
| Size limit | **FIXED** | 100 MB max enforced |
| Filename sanitization | **FIXED** | Regex strips special chars |
| Auth required | OK | `get_current_user` dependency |

## 8. Authentication

| Check | Status | Detail |
|-------|--------|--------|
| Password hashing | OK | bcrypt |
| Token hashing | OK | SHA-256 for refresh tokens |
| JWT secret validation | OK | Blocked in production if weak |
| Session management | OK | Expiration + revocation |
| Audit logging | OK | Security events logged |

## 9. Website Security

| Check | Status |
|-------|--------|
| No API keys in frontend | PASS |
| No localhost references | PASS |
| No fake data | PASS |
| CSP meta tag | PASS |
| X-Frame-Options | PASS |
| Download links to real GitHub | PASS |
| No analytics/tracking | PASS |

## 10. Known Remaining Items

| Item | Priority | Note |
|------|----------|------|
| CloudFront HTTPS | Medium | Requires AWS account verification |
| Spend caps on AI providers | Low | Would need per-user quota tracking |
| CSRF protection | N/A | Bearer token auth, no cookies |
| Secure cookies | N/A | DASH does not use cookies |
| Debug mode from internet | OK | Defaults to False, blocked in production |
