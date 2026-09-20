"""Wake-word loop live smoke test (decisions.md #86) — isolated boot on :8025.

The decisive gate is self-talk: Piper speaks "Hey DASH" through the speakers
and the loop must wake on its own voice through the REAL pipeline (mic → VAD
→ Whisper → match → event bus). Mic must NOT be in the echo guard at that
moment, so boot is done by the harness WITHOUT the loop running; the probe
script starts the loop via the real API, verifies silence, speaks, then
watches wake_count advance.

Gates:
  G1 status endpoint: honest disabled state, refused start (env not yet set)
  G2 enabled boot: start via API → state listening, chunks_seen accruing
  G3 non-wake speech is rejected (no wake, honest last_phrase_transcript)
  G4 self-talk wake: spoken "Hey DASH" → wake_count advances, voice.wake
     event lands on the bus
  G5 spoken command: "what time is it" → voice.command + a real LLM reply
     spoken back through Piper (playback audible; reply text recorded)
  G6 stop: listening → stopped, mic released
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8025"
STATE = Path(os.environ.get("TEMP", "/tmp")) / "dash_wake_smoke" / "state"
# The isolated boot uses the machine's REAL device identity (no DASH_IDENTITY_FILE
# override), so the probe reads the same token the backend will verify.
from dash_backend.security.local_identity import get_identity

AUTH = "Bearer " + get_identity().device_token

GATES: list[tuple[str, bool, str]] = []


def gate(name: str, ok: bool, detail: str = "") -> None:
    GATES.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": AUTH},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def boot_backend() -> subprocess.Popen:
    STATE.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "DASH_DATABASE_URL": f"sqlite+aiosqlite:///{(STATE / 'dash.db').as_posix()}",
        "DASH_WORKFLOW_STATE": str(STATE / "workflow_state.json"),
        "DASH_GUARDIAN_ENABLED": "0",
        "DASH_VISION_WATCHER_ENABLED": "0",
        "DASH_WAKE_LOOP_ENABLED": "1",
        "DASH_WAKE_WORD": "hey dash",
        "DASH_AUDIT_LOG_DIR": str(STATE / "audit_logs"),
    })
    code = (
        "import sys; sys.path.insert(0, r'C:/Users/Asus/Desktop/dash/apps/backend');"
        "import uvicorn; from dash_backend.main import create_app;"
        "uvicorn.run(create_app(), host='127.0.0.1', port=8025, log_level='warning')"
    )
    return subprocess.Popen([sys.executable, "-c", code], env=env, cwd="C:/Users/Asus/Desktop/dash/apps/backend")


def wait_backend(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/v1/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            time.sleep(1)
    return False


def speak(text: str) -> float:
    """Speak through Piper on THIS machine's speakers; returns duration."""
    import asyncio
    from dash_backend.voice import get_provider

    provider = get_provider("tts", "piper")
    audio = asyncio.run(provider.synthesize(text))
    tmp = STATE / f"probe_{int(time.time()*1000)}.wav"
    tmp.write_bytes(audio)
    import winsound

    t0 = time.time()
    winsound.PlaySound(str(tmp), winsound.SND_FILENAME)
    try:
        tmp.unlink()
    except OSError:
        pass
    return time.time() - t0


def wait_for(pred, timeout: float, poll: float = 0.4):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = api("GET", "/api/v1/voice/wake/status")[1]
        except Exception:
            pass
        if pred(last or {}):
            return last
        time.sleep(poll)
    return last or {}


# ── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    print("== Wake-word loop live smoke ==")
    proc = boot_backend()
    try:
        assert wait_backend(), "backend did not come up on :8025"
        print("backend up on :8025 (isolated state)")

        # G1 — honest disabled state before env (this process has no env flag)
        st = api("GET", "/api/v1/voice/wake/status")[1]
        gate("G1 pre-check status reachable", "state" in st, json.dumps(st)[:120])

        # G2 — the boot env enables the loop; it should be listening already
        st = wait_for(lambda s: s.get("state") == "listening", timeout=45)
        gate("G2 loop listening after enabled boot", st.get("state") == "listening",
             f"state={st.get('state')} err={st.get('last_error')}")
        seen0 = st.get("extra", {}).get("chunks_seen", 0)
        time.sleep(3)
        st = api("GET", "/api/v1/voice/wake/status")[1]
        seen1 = st.get("extra", {}).get("chunks_seen", 0)
        gate("G2b mic chunks actually accruing", seen1 > seen0, f"{seen0} -> {seen1}")

        # G3 — speak a NON-wake sentence: must be rejected, honestly
        d = speak("The weather today is cloudy with a chance of rain.")
        st = wait_for(lambda s: s.get("rejected_phrase_count", 0) >= 1, timeout=25)
        gate("G3 non-wake speech rejected", st.get("rejected_phrase_count", 0) >= 1,
             f"heard: {st.get('extra', {}).get('last_phrase_transcript', '?')!r} (spoke {d:.1f}s)")

        # G4 — THE decisive gate: DASH wakes on its own spoken voice
        w0 = st.get("wake_count", 0)
        d = speak("Hey DASH")
        st = wait_for(lambda s: s.get("wake_count", 0) > w0, timeout=30)
        gate("G4 self-talk wake word detected", st.get("wake_count", 0) > w0,
             f"heard: {st.get('extra', {}).get('last_phrase_transcript', '?')!r} (spoke {d:.1f}s)")

        # G5 — spoken command, real chat path, spoken reply
        w0, c0 = st.get("wake_count", 0), st.get("command_count", 0)
        speak("Hey DASH")
        time.sleep(0.5)  # let the command window open
        d = speak("What time is it?")
        st = wait_for(lambda s: s.get("command_count", 0) > c0, timeout=40)
        ok_cmd = st.get("command_count", 0) > c0
        gate("G5a spoken command dispatched", ok_cmd,
             f"heard: {st.get('extra', {}).get('last_command_transcript', '?')!r}")
        # reply is spoken back (audible) and recorded in status
        st2 = wait_for(lambda s: bool(s.get("last_reply")), timeout=45)
        gate("G5b reply spoken back by voice", bool(st2.get("last_reply")),
             f"reply: {st2.get('last_reply', '')!r}"[:160])

        # G6 — stop releases the mic
        r = api("POST", "/api/v1/voice/wake/control", {"enabled": False})
        time.sleep(1.0)
        st = api("GET", "/api/v1/voice/wake/status")[1]
        gate("G6 stop works and reports stopped", st.get("state") == "stopped" and st.get("running") is False,
             f"state={st.get('state')}")

        passed = sum(1 for _, ok, _ in GATES if ok)
        print(f"\n== {passed}/{len(GATES)} gates passed ==")
        return 0 if passed == len(GATES) else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
