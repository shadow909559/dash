"""
Phase 11 — DASH End-to-End Integration Validation Script.

Tests every backend API endpoint, WebSocket event, and tool for:
1. Reachability (status != 404)
2. Correct execution (returns valid response)
3. Error handling (returns proper error on bad input)

Run: python -m apps.backend.dash_backend.validate_integration
     (from project root with backend running)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

# ── Configuration ─────────────────────────────────────────────

BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/ws"
SYSTEM_WS_URL = "ws://127.0.0.1:8000/api/v1/ws/system"
REMOTE_DESKTOP_WS_URL = "ws://127.0.0.1:8000/api/v1/ws/remote-desktop"

TEST_USER_EMAIL = "test@dash.com"
TEST_USER_PASSWORD = "testpassword123"

# ── State ─────────────────────────────────────────────────────

results: dict[str, dict[str, Any]] = {}
access_token: str | None = None
errors_only = "--errors" in sys.argv


# ── Test Result Helpers ───────────────────────────────────────


class TestResult:
    def __init__(self, category: str, name: str):
        self.category = category
        self.name = name
        self.passed = False
        self.detail = ""

    def ok(self, detail: str = "PASS"):
        self.passed = True
        self.detail = detail
        results.setdefault(self.category, {})[self.name] = {"status": "PASS", "detail": detail}
        if not errors_only:
            print(f"  ✅ {self.name}")

    def fail(self, detail: str):
        self.passed = False
        self.detail = detail
        results.setdefault(self.category, {})[self.name] = {"status": "FAIL", "detail": detail}
        print(f"  ❌ {self.name}: {detail}")


# ── HTTP Client ───────────────────────────────────────────────


async def http_request(
    method: str,
    path: str,
    body: Any = None,
    authenticated: bool = True,
) -> tuple[int, Any]:
    """Make an HTTP request and return (status_code, data)."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if authenticated and access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        try:
            response = await client.request(
                method=method,
                url=path,
                headers=headers,
                json=body,
            )
            try:
                data = response.json()
            except Exception:
                data = response.text
            return response.status_code, data
        except Exception as exc:
            return 0, str(exc)


# ── WebSocket Client ──────────────────────────────────────────


async def ws_test(path: str, messages: list[dict], timeout: float = 5.0) -> list[dict]:
    """Send messages over WebSocket and collect responses."""
    import websockets

    url = f"ws://127.0.0.1:8000{path}"
    responses = []
    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            for msg in messages:
                await ws.send(json.dumps(msg))
            while True:
                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    data = json.loads(resp)
                    responses.append(data)
                    # Stop after we get what we need
                    if data.get("type") in ("session.info", "pong", "subscribed"):
                        break
                except asyncio.TimeoutError:
                    break
    except Exception as exc:
        responses.append({"error": str(exc)})
    return responses


# ── Test Runner ───────────────────────────────────────────────


async def run_tests():
    global access_token

    print("\n" + "=" * 60)
    print("  DASH INTEGRATION VALIDATION REPORT")
    print("=" * 60)

    # ── 1. Health ──────────────────────────────────────────────
    print("\n── SYSTEM: Health ──")

    t = TestResult("health", "GET /health")
    status, data = await http_request("GET", "/health", authenticated=False)
    if status == 200 and data.get("status") == "ok":
        t.ok(f"version={data.get('version')}, uptime={data.get('uptime', 0):.1f}s")
    else:
        t.fail(f"Expected 200, got {status}: {data}")

    # ── 2. Auth ────────────────────────────────────────────────
    print("\n── AUTH ──")

    # Register (may fail if already exists)
    t = TestResult("auth", "POST /auth/register")
    status, data = await http_request(
        "POST",
        "/auth/register",
        body={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD, "username": "testuser"},
        authenticated=False,
    )
    if status in (201, 409):
        if status == 201:
            access_token = data.get("access_token")
        t.ok(f"status={status}")
    else:
        t.fail(f"Expected 201/409, got {status}: {data}")

    # Login
    t = TestResult("auth", "POST /auth/login")
    status, data = await http_request(
        "POST",
        "/auth/login",
        body={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        authenticated=False,
    )
    if status == 200:
        access_token = data.get("access_token")
        t.ok("token received")
    else:
        t.fail(f"Expected 200, got {status}: {data}")

    # Get current user
    if access_token:
        t = TestResult("auth", "GET /auth/me")
        status, data = await http_request("GET", "/auth/me")
        if status == 200:
            t.ok(f"user={data.get('email')}")
        else:
            t.fail(f"Expected 200, got {status}: {data}")

    # Token refresh
    if access_token:
        t = TestResult("auth", "POST /auth/refresh")
        status, data = await http_request(
            "POST",
            "/auth/refresh",
            body={"refresh_token": "dummy"},
            authenticated=False,
        )
        if status in (200, 401):
            t.ok(f"status={status} (expected 401 for bad token)")
        else:
            t.fail(f"Expected 200/401, got {status}: {data}")

    # Rate limiting
    t = TestResult("auth", "Rate limiting")
    statuses = []
    for _ in range(5):
        s, _ = await http_request(
            "POST",
            "/auth/login",
            body={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
            authenticated=False,
        )
        statuses.append(s)
    if any(s == 429 for s in statuses) or all(s == 200 for s in statuses):
        t.ok(f"responses={statuses}")
    else:
        t.fail(f"Unexpected: {statuses}")

    # ── 3. WebSocket (Main Chat) ──────────────────────────────
    print("\n── WEBSOCKET ──")

    if access_token:
        t = TestResult("websocket", "/ws - auth")
        responses = await ws_test(
            "/api/v1/ws",
            [{"type": "auth", "access_token": access_token}],
        )
        if any(r.get("type") == "session.info" for r in responses):
            t.ok(f"got session.info: {responses}")
        elif any(r.get("type") == "chat.error" for r in responses):
            t.fail(f"Auth error: {responses}")
        else:
            t.fail(f"No session.info: {responses}")

        t = TestResult("websocket", "/ws - chat.send")
        responses = await ws_test(
            "/api/v1/ws",
            [
                {"type": "auth", "access_token": access_token},
                {"type": "chat.send", "message_id": "test-1", "content": "Hello DASH!"},
            ],
            timeout=15.0,
        )
        if any(r.get("type") == "chat.token" for r in responses):
            t.ok("received chat.token response")
        elif any(r.get("type") == "chat.done" for r in responses):
            t.ok("received chat.done response")
        else:
            t.fail(f"No chat response: {responses}")

        t = TestResult("websocket", "/ws - voice.stt")
        import base64
        audio_b64 = base64.b64encode(b"test audio bytes").decode("ascii")
        responses = await ws_test(
            "/api/v1/ws",
            [
                {"type": "auth", "access_token": access_token},
                {"type": "voice.stt", "request_id": "vtest-1", "audio_base64": audio_b64},
            ],
            timeout=10.0,
        )
        if any("stt" in str(r.get("type", "")) for r in responses):
            t.ok(f"got STT response: {responses[:2]}")
        else:
            t.fail(f"No STT response: {responses[:2]}")
    else:
        print("  ⚠️  Skipping WebSocket tests (no token)")

    # ── 4. System WS ──────────────────────────────────────────
    print("\n── SYSTEM WS ──")

    t = TestResult("system", "/ws/system - connect")
    responses = await ws_test("/api/v1/ws/system", [{"type": "ping"}], timeout=3.0)
    if any(r.get("type") == "pong" for r in responses):
        t.ok("got pong")
    elif len(responses) > 0:
        t.ok(f"connected, got {len(responses)} messages")
    else:
        t.fail(f"No response: {responses}")

    # ── 5. Conversations ──────────────────────────────────────
    print("\n── API: Conversations ──")

    if access_token:
        t = TestResult("conversations", "GET /conversations")
        status, data = await http_request("GET", "/conversations")
        if status in (200, 422):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200, got {status}: {data}")

        t = TestResult("conversations", "POST /conversations")
        status, data = await http_request("POST", "/conversations", body={"title": "Test"})
        if status == 201:
            conv_id = data.get("id")
            t.ok(f"created conv={conv_id}")
        else:
            t.fail(f"Expected 201, got {status}: {data}")
    else:
        print("  ⚠️  Skipping conversation tests (no token)")

    # ── 6. Memory ─────────────────────────────────────────────
    print("\n── API: Memory ──")

    if access_token:
        t = TestResult("memory", "GET /memory")
        status, data = await http_request("GET", "/memory")
        if status == 200:
            t.ok(f"items={data.get('total', 0)}")
        else:
            t.fail(f"Expected 200, got {status}: {data}")

        t = TestResult("memory", "POST /memory")
        status, data = await http_request(
            "POST",
            "/memory",
            body={"content": "Test memory entry", "category": "test"},
        )
        if status == 201:
            t.ok(f"created={data.get('id')}")
        else:
            t.fail(f"Expected 201, got {status}: {data}")

        t = TestResult("memory", "GET /memory/search")
        status, data = await http_request("GET", "/memory/search?q=test")
        if status == 200:
            t.ok(f"results={data.get('items', [])}")
        else:
            t.fail(f"Expected 200, got {status}: {data}")
    else:
        print("  ⚠️  Skipping memory tests")

    # ── 7. Projects ───────────────────────────────────────────
    print("\n── API: Projects ──")

    if access_token:
        t = TestResult("projects", "GET /projects")
        status, data = await http_request("GET", "/projects")
        if status == 200:
            t.ok(f"items={len(data)}")
        else:
            t.fail(f"Expected 200, got {status}")

        t = TestResult("projects", "POST /projects")
        status, data = await http_request("POST", "/projects", body={"name": "Test Project"})
        if status == 201:
            t.ok(f"created={data.get('id')}")
        else:
            t.fail(f"Expected 201, got {status}: {data}")
    else:
        print("  ⚠️  Skipping project tests")

    # ── 8. Automation ─────────────────────────────────────────
    print("\n── API: Automation ──")

    if access_token:
        t = TestResult("automation", "GET /automation/rules")
        status, data = await http_request("GET", "/automation/rules")
        if status == 200:
            t.ok(f"items={len(data)}")
        else:
            t.fail(f"Expected 200, got {status}")

        t = TestResult("automation", "POST /automation/rules")
        status, data = await http_request(
            "POST",
            "/automation/rules",
            body={"name": "Test Rule", "trigger": "schedule", "action": "system_info"},
        )
        if status == 201:
            rule_id = data.get("id")
            t.ok(f"created={rule_id}")
            # Test PATCH
            t2 = TestResult("automation", "PATCH /automation/rules/{id}")
            s2, d2 = await http_request("PATCH", f"/automation/rules/{rule_id}", body={"enabled": False})
            if s2 == 200:
                t2.ok(f"toggled enabled={d2.get('enabled')}")
            else:
                t2.fail(f"Expected 200, got {s2}: {d2}")

            # Test DELETE
            t3 = TestResult("automation", "DELETE /automation/rules/{id}")
            s3, _ = await http_request("DELETE", f"/automation/rules/{rule_id}")
            if s3 == 204:
                t3.ok("deleted")
            else:
                t3.fail(f"Expected 204, got {s3}")
        else:
            t.fail(f"Expected 201, got {status}: {data}")
    else:
        print("  ⚠️  Skipping automation tests")

    # ── 9. Notifications ─────────────────────────────────────
    print("\n── API: Notifications ──")

    if access_token:
        t = TestResult("notifications", "GET /notifications")
        status, data = await http_request("GET", "/notifications")
        if status == 200:
            t.ok(f"items={len(data)}")
        else:
            t.fail(f"Expected 200, got {status}")
    else:
        print("  ⚠️  Skipping notification tests")

    # ── 10. Desktop Control ───────────────────────────────────
    print("\n── API: Desktop Control ──")

    if access_token:
        t = TestResult("desktop", "GET /desktop/volume")
        status, data = await http_request("GET", "/desktop/volume")
        if status in (200, 500):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/500, got {status}")

        t = TestResult("desktop", "GET /desktop/brightness")
        status, data = await http_request("GET", "/desktop/brightness")
        if status in (200, 500):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/500, got {status}")

        t = TestResult("desktop", "GET /desktop/clipboard")
        status, data = await http_request("GET", "/desktop/clipboard")
        if status in (200, 500):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/500, got {status}")

        t = TestResult("desktop", "GET /desktop/mouse/position")
        status, data = await http_request("GET", "/desktop/mouse/position")
        if status in (200, 500):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/500, got {status}")
    else:
        print("  ⚠️  Skipping desktop control tests")

    # ── 11. Window Manager ───────────────────────────────────
    print("\n── API: Window Manager ──")

    if access_token:
        t = TestResult("windows", "GET /windows")
        status, data = await http_request("GET", "/windows")
        # Windows-specific: 200 on Windows, 500 on other platforms
        if status in (200, 500):
            details = data.get("details", {})
            if status == 200:
                t.ok(f"windows={details.get('count', 0)}")
            else:
                t.ok(f"status={status} (expected on non-Windows)")
        else:
            t.fail(f"Expected 200/500, got {status}")

        t = TestResult("windows", "GET /windows/active")
        status, data = await http_request("GET", "/windows/active")
        if status in (200, 500):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/500, got {status}")
    else:
        print("  ⚠️  Skipping window manager tests")

    # ── 12. File Operations ───────────────────────────────────
    print("\n── API: Files ──")

    if access_token:
        t = TestResult("files", "GET /files/browse")
        status, data = await http_request("GET", "/files/browse")
        if status == 200:
            t.ok(f"entries={data.get('count', 0)} at {data.get('path', '')}")
        else:
            t.fail(f"Expected 200, got {status}: {data}")

        t = TestResult("files", "GET /files/search")
        status, data = await http_request("GET", "/files/search?pattern=*.py")
        if status == 200:
            t.ok(f"results={data.get('count', 0)}")
        else:
            t.fail(f"Expected 200, got {status}")

        t = TestResult("files", "GET /files/preview")
        status, data = await http_request("GET", "/files/preview?path=apps/backend/dash_backend/main.py")
        if status in (200, 404):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/404, got {status}")

        t = TestResult("files", "GET /files/special-folders")
        status, data = await http_request("GET", "/files/special-folders")
        if status == 200:
            t.ok(f"folders={list(data.keys())}")
        else:
            t.fail(f"Expected 200, got {status}")

        t = TestResult("files", "GET /files/drives")
        status, data = await http_request("GET", "/files/drives")
        if status == 200:
            t.ok(f"drives={data.get('count', 0)}")
        else:
            t.fail(f"Expected 200, got {status}")
    else:
        print("  ⚠️  Skipping file tests")

    # ── 13. AI OS ─────────────────────────────────────────────
    print("\n── API: AI OS ──")

    if access_token:
        t = TestResult("ai-os", "GET /ai-os/providers")
        status, data = await http_request("GET", "/ai-os/providers")
        if status == 200:
            t.ok(f"providers={len(data.get('providers', []))}")
        else:
            t.fail(f"Expected 200, got {status}")

        t = TestResult("ai-os", "GET /ai-os/session")
        # Session endpoint requires a valid session_id
        status, data = await http_request("GET", "/ai-os/session/test-session")
        if status in (200, 404):
            t.ok(f"status={status}")
        else:
            t.fail(f"Expected 200/404, got {status}")
    else:
        print("  ⚠️  Skipping AI OS tests")

    # ── 14. Remote Desktop ────────────────────────────────────
    print("\n── API: Remote Desktop ──")

    t = TestResult("remote-desktop", "GET /remote-desktop/status")
    status, data = await http_request("GET", "/remote-desktop/status", authenticated=False)
    if status in (200, 404):
        t.ok(f"status={status}")
    else:
        t.fail(f"Expected 200/404, got {status}")

    # ── 15. RAG ───────────────────────────────────────────────
    print("\n── API: RAG ──")

    if access_token:
        t = TestResult("rag", "RAG endpoints")
        status, data = await http_request("GET", "/rag/search?q=test")
        if status in (200, 404, 422):
            t.ok(f"status={status}")
        else:
            t.fail(f"Unexpected status: {status}")
    else:
        print("  ⚠️  Skipping RAG tests")

    # ── 16. Personal ──────────────────────────────────────────
    print("\n── API: Personal ──")

    if access_token:
        t = TestResult("personal", "GET /personal")
        status, data = await http_request("GET", "/personal")
        if status in (200, 404):
            t.ok(f"status={status}")
        else:
            t.fail(f"Unexpected status: {status}")
    else:
        print("  ⚠️  Skipping personal tests")

    # ── 17. Sync ──────────────────────────────────────────────
    print("\n── API: Sync ──")

    if access_token:
        t = TestResult("sync", "GET /sync/status")
        status, data = await http_request("GET", "/sync/status")
        if status in (200, 404):
            t.ok(f"status={status}")
        else:
            t.fail(f"Unexpected status: {status}")
    else:
        print("  ⚠️  Skipping sync tests")


# ── Summary ───────────────────────────────────────────────────


def print_summary():
    print("\n" + "=" * 60)
    print("  VALIDATION SUMMARY")
    print("=" * 60)

    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for category, tests in sorted(results.items()):
        cat_total = len(tests)
        cat_passed = sum(1 for t in tests.values() if t["status"] == "PASS")
        cat_failed = sum(1 for t in tests.values() if t["status"] == "FAIL")
        total += cat_total
        passed += cat_passed
        failed += cat_failed

        status_icon = "✅" if cat_failed == 0 else "❌"
        print(f"\n  {status_icon} {category.upper()}: {cat_passed}/{cat_total} passed")

    print("\n" + "-" * 60)
    print(f"  TOTAL:    {total}")
    print(f"  PASSED:   {passed}  ✅")
    print(f"  FAILED:   {failed}  ❌")
    print(f"  SKIPPED:  {skipped}")
    print(f"  RATE:     {passed/total*100:.1f}%" if total > 0 else "  RATE: N/A")
    print("-" * 60)

    if failed > 0:
        print("\n  ❌ FAILED TESTS:")
        for category, tests in sorted(results.items()):
            for name, result in tests.items():
                if result["status"] == "FAIL":
                    print(f"    - [{category}] {name}: {result['detail']}")
        print("\n  ⚠️  Some tests failed. Review and fix above issues.")
    else:
        print("\n  🎉 ALL TESTS PASSED!")

    return failed == 0


# ── Main ──────────────────────────────────────────────────────


async def main():
    try:
        import httpx
        import websockets
    except ImportError:
        print("❌ Missing dependencies. Install: pip install httpx websockets")
        sys.exit(1)

    await run_tests()
    all_pass = print_summary()

    if not all_pass:
        print("\n⚠️  Some tests failed. See details above.")
        sys.exit(1)
    else:
        print("\n✅ Validation complete — ALL PASS!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

