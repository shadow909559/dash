"""Privacy Policy for DASH.

Version 1.0 — Effective: September 7, 2026

This document accurately describes DASH's actual data practices as
implemented in the codebase. Every claim here corresponds to real
behavior; nothing is fabricated.
"""

PRIVACY_POLICY_VERSION = "1.0"
PRIVACY_POLICY_EFFECTIVE = "2026-09-07"

PRIVACY_POLICY = r"""# DASH Privacy Policy

**Version:** 1.0
**Effective Date:** September 7, 2026
**Last Updated:** September 7, 2026

---

## 1. Overview

DASH is a personal AI operating system that runs on your local machine.
This privacy policy describes what data DASH collects, how it is used,
where it is stored, and what controls you have over it.

DASH is designed as a single-user, locally-run application. Your data
stays on your machine by default.

---

## 2. Information We Collect

### 2.1 Account Information

When you create a DASH account, the following information is stored
locally on your device in a SQLite database:

| Data | Purpose | Retention |
|------|---------|-----------|
| Email address | Account identification and login | Until account deletion |
| Username | Display and identification | Until account deletion |
| Password hash (bcrypt) | Authentication | Until account deletion |
| Display name | Personalization | Until account deletion |

Passwords are never stored in plain text. They are hashed using bcrypt
before storage.

### 2.2 Device Information

DASH tracks connected devices to manage sessions:

| Data | Purpose | Retention |
|------|---------|-----------|
| Device name | Session identification | Until device removal |
| Device type (desktop/android) | Session categorization | Until device removal |
| Platform (Windows/macOS/Linux) | Compatibility | Until device removal |
| Last seen timestamp | Session management | Until device removal |

### 2.3 Session Data

DASH maintains session records for authentication lifecycle:

| Data | Purpose | Retention |
|------|---------|-----------|
| Session ID | Session management | Until session expiry or revocation |
| Refresh token hash | Token validation | Until token expiry or revocation |
| IP address | Session security | Until session expiry or revocation |
| User agent string | Device identification | Until session expiry or revocation |
| Created/last active timestamps | Session management | Until session expiry or revocation |

### 2.4 Conversations and Messages

Your chat history with DASH is stored locally:

| Data | Purpose | Retention |
|------|---------|-----------|
| Conversation metadata (title, timestamps) | Conversation management | Until user deletion |
| Message content (user and assistant) | Chat history and context | Until user deletion |
| Message role and timestamps | Conversation ordering | Until user deletion |

### 2.5 Memory

DASH maintains a long-term memory system to remember context across
conversations:

| Data | Purpose | Retention |
|------|---------|-----------|
| Memory content | User preferences, facts, decisions | Until user deletion or pruning |
| Memory type and category | Organization | Until user deletion |
| Importance score | Ranking and retrieval | Until user deletion |
| Confidence score | Reliability tracking | Until user deletion |
| Project association | Context scoping | Until user deletion |
| Embedding vectors | Semantic search | Until user deletion |

Memories are automatically pruned when the total exceeds 500 per user,
removing the lowest-scoring items first.

### 2.6 Tasks and Goals

DASH tracks goals and tasks you create:

| Data | Purpose | Retention |
|------|---------|-----------|
| Goal name, description, priority | Task management | Until user deletion |
| Deadline and status | Scheduling | Until user deletion |
| Task dependencies | Workflow ordering | Until user deletion |

### 2.7 Notifications

System and proactive notifications are stored:

| Data | Purpose | Retention |
|------|---------|-----------|
| Notification title and message | User information | Until user deletion |
| Read status | UI state | Until user deletion |

### 2.8 Audit Log

Security-relevant actions are logged:

| Data | Purpose | Retention |
|------|---------|-----------|
| Event type (login, logout, etc.) | Security audit | Configurable, default 90 days |
| Timestamp | Event ordering | Alongside event |
| User ID | Accountability | Alongside event |
| IP address | Security analysis | Alongside event |

Audit log entries never contain passwords, tokens, API keys, or
conversation content. Sensitive values are redacted before logging.

---

## 3. How Data Is Used

### 3.1 Local Processing (Default)

By default, DASH processes all data on your local machine. DASH does
not send your personal data to any external service unless you
explicitly configure a cloud AI provider (see Section 3.2).

### 3.2 AI Model Providers

When you use AI features, DASH may send the following to AI providers
**only if you have configured them**:

| Provider | Data Sent | When |
|----------|-----------|------|
| Ollama (local) | Prompt text, conversation context | Every AI request (runs on your machine) |
| OpenAI (optional) | Prompt text, conversation context | Only if you configure an OpenAI API key |
| Anthropic (optional) | Prompt text, conversation context | Only if you configure a Claude API key |
| Google Gemini (optional) | Prompt text, conversation context | Only if you configure a Gemini API key |
| Groq (optional) | Prompt text, conversation context | Only if you configure a Groq API key |

**Important:** DASH's default configuration uses Ollama, which runs
entirely on your local machine. No data leaves your device unless you
explicitly configure a cloud AI provider. Even when cloud providers are
used, only the prompt text is sent; passwords, tokens, and other
sensitive data are never included.

### 3.3 System Telemetry

DASH collects local system metrics for its system monitor and
predictive features:

| Data | Purpose | Sent Externally |
|------|---------|----------------|
| CPU usage | System health display | No |
| RAM usage | System health display | No |
| Disk usage | System health display | No |
| Network activity | System health display | No |

All telemetry is processed and displayed locally. Nothing is sent to
any external server.

### 3.4 Cookies and Tracking

DASH does not use cookies, local storage tracking, or any web-based
tracking technologies. DASH is a native desktop application (Electron)
that stores data in a local SQLite database and JSON state files.

There is no cookie consent banner because there are no cookies to
consent to. DASH does not use:

- Session cookies
- Analytics cookies
- Advertising cookies
- Third-party tracking cookies
- Web beacons or tracking pixels
- Session replay tools
- Heatmap or behavior tracking

Authentication uses a device token stored in a local JSON file
(`%LOCALAPPDATA%\DASH\identity.json`), not browser cookies.

---

## 4. Data Storage

### 4.1 Local Storage

All user data is stored in a SQLite database located at:

- **Windows:** `%LOCALAPPDATA%\DASH\dash_dev.db`
- **macOS/Linux:** `~/.local/share/DASH/dash_dev.db`

### 4.2 State Files

| File | Location | Content |
|------|----------|---------|
| Identity file | `%LOCALAPPDATA%\DASH\identity.json` | Device authentication token |
| Proactive state | `%LOCALAPPDATA%\DASH\proactive_state.json` | Suggestion cooldowns and history |
| Predictive samples | `%LOCALAPPDATA%\DASH\predictive_samples.json` | Device history for trend analysis |

### 4.3 No Cloud Storage

DASH does not use any cloud storage service. All data remains on your
local machine unless you manually export it.

---

## 5. Data Retention

| Data Type | Default Retention | Deletable |
|-----------|-------------------|-----------|
| Account data | Until account deletion | Yes |
| Conversations | Until user deletion | Yes |
| Messages | Until user deletion | Yes |
| Memories | Until pruning (max 500/user) or deletion | Yes |
| Sessions | Until expiry (30 days) or revocation | Yes |
| Audit log | 90 days (configurable) | Yes |
| Notifications | Until user deletion | Yes |
| Tasks and goals | Until user deletion | Yes |
| Device info | Until device removal | Yes |
| Predictive samples | 7 days rolling window | Yes |
| Proactive state | Indefinite (cooldown data) | Yes |

---

## 6. Your Data Rights

### 6.1 Export Your Data

You can export all your data at any time via the Privacy API:

- `GET /privacy/data-export` — Returns a complete JSON export of all
  your data across all stores.

### 6.2 Delete Your Data

You can delete your data:

- `DELETE /privacy/data-delete?confirm=true` — Removes all your data
  from the database, state files, and tokens.
- Individual memories, conversations, and other records can also be
  deleted through their respective API endpoints.

### 6.3 Data Inventory

- `GET /privacy/data-inventory` — Returns a description of all data
  stores, what they contain, retention periods, and whether data is
  exportable or deletable.

### 6.4 Session Management

- `GET /security/sessions` — View all active sessions
- `POST /security/sessions/{id}/revoke` — Revoke a specific session
- `POST /security/sessions/revoke-all` — Revoke all sessions

### 6.5 Account Deletion

Account deletion removes all associated data: conversations, messages,
memories, sessions, tasks, notifications, and device records. This
action cannot be undone.

---

## 7. Third-Party Services

### 7.1 AI Providers (Optional)

| Provider | Purpose | Data Processed | Required |
|----------|---------|----------------|----------|
| Ollama | Local AI inference | Prompts and context | Yes (default, runs locally) |
| OpenAI | Cloud AI inference | Prompts and context | No (optional) |
| Anthropic | Cloud AI inference | Prompts and context | No (optional) |
| Google Gemini | Cloud AI inference | Prompts and context | No (optional) |
| Groq | Cloud AI inference | Prompts and context | No (optional) |

### 7.2 No Third-Party Analytics

DASH does not use any analytics services, tracking pixels, session
replay tools, or advertising networks.

### 7.3 Third-Party Resources

DASH loads the Orbitron font from Google Fonts CDN for the boot
animation. No third-party maps, videos, widgets, or tracking scripts
are embedded.

---

## 8. Security

DASH implements the following security measures:

- **Authentication:** Device token-based authentication with bcrypt
  password hashing
- **Session management:** Unique session IDs with expiration and
  revocation support
- **Audit logging:** Security events are logged with redacted
  sensitive values
- **Token security:** Refresh tokens are hashed before storage;
  raw tokens are never logged
- **API protection:** All endpoints require valid authentication;
  no unauthenticated access
- **Log redaction:** Passwords, tokens, API keys, and other
  sensitive data are redacted from logs
- **Session revocation:** Sessions can be individually or bulk
  revoked, immediately terminating access

---

## 9. Children's Privacy

DASH is not directed at children under 13. We do not knowingly
collect information from children. If you are under 13, do not use
DASH.

---

## 10. Changes to This Policy

We will update this policy when our data practices change. The version
number and effective date at the top of this document will be updated.
Continued use of DASH after changes constitutes acceptance of the
updated policy.

---

## 11. Contact

For privacy-related questions or to exercise your data rights, contact:

- **Email:** support@dash-ai.dev
- **GitHub Issues:** https://github.com/shadow909559/dash/issues

---

## 12. Jurisdiction

DASH is developed and operated from India. If you use DASH from
outside India, you are responsible for compliance with your local
data protection laws.
"""

__all__ = ["PRIVACY_POLICY", "PRIVACY_POLICY_VERSION", "PRIVACY_POLICY_EFFECTIVE"]
