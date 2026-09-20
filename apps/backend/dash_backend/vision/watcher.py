"""VisionWatcher — DASH's autonomous eyes (Phase 1 extension, decisions.md #62).

The camera pipeline (recognition.py, camera_vision.py) already sees and
recognizes people on demand. This module makes DASH look *on his own*: a
polling loop captures a frame, recognizes enrolled persons, and reports
what happened — through AgentCore's working memory (so it lands in the
same context DASH reasons from), the event bus (so workflows can react),
and the audit log (so the record is honest whether or not anyone listens).

Honesty contract, enforced by tests:
- Every state has a named cause: no camera → the capture error verbatim;
  missing models → the exact reason from the recognition service; an
  unrecognized face → "not enrolled", never a guessed identity.
- "Recognized Alice" is only ever emitted when cosine similarity cleared
  the enrollment threshold — the watcher never names someone itself.
- Repetition is rate-limited per event key (a person sitting in front of
  the camera does not become a notification flood), and repeated capture
  failures back the poll off instead of hammering a dead device.
- Every cycle is recorded with what was seen and what was delivered;
  a report that could not reach the brain is marked as such, not lost.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_S = 30.0
MIN_INTERVAL_S = 5.0
FAILURE_BACKOFF_MAX = 32.0  # interval × 32 ceiling: 30s → 16min when blind
REPEAT_COOLDOWN_S = 600.0   # per event key; bounded reporting, not silence
EVENT_HISTORY_MAX = 100
MIN_COOLDOWN_S = 0.0        # 0 = every matched sighting is reported
MAX_CAMERA_ID = 32
WATCHER_CONFIG_VERSION = 1
NOTIFY_COOLDOWN_S = 300.0   # desktop-toast rate limit, independent of the
                            # event cooldown (guardian's pattern: 300s)
TOAST_EVENT_KINDS = ("person_seen",)  # kinds eligible for a desktop toast;
                                      # person_seen today, more only when each
                                      # earns its own honest wording

KNOWN_EVENT_KINDS = (
    "person_seen",         # enrolled person matched above threshold
    "unknown_person",      # face detected, no enrolled match
    "scene",               # objects only, no faces
    "camera_unavailable",  # capture failed — cause named verbatim
    "watch_degraded",      # cannot analyze — models/decode, reason named
    "watch_recovered",     # cycles failed before, this one succeeded
)


class VisionWatcher:
    """Polling camera watch: capture → analyze → recognize → report."""

    def __init__(
        self,
        interval_seconds: float = DEFAULT_INTERVAL_S,
        repeat_cooldown_s: float = REPEAT_COOLDOWN_S,
        camera_id: int = 0,
        camera: Any = None,
        recognizer: Any = None,
        detector: Any = None,
        brain: Any = None,
        bus: Any = None,
        store_path: Optional[Path] = None,
    ) -> None:
        self._interval = max(MIN_INTERVAL_S, float(interval_seconds))
        self._cooldown_s = float(repeat_cooldown_s)
        self._camera_id = int(camera_id)
        self._camera = camera
        self._recognizer = recognizer
        self._detector = detector
        self._brain = brain
        self._bus = bus
        # Demo seam: a static frame source (DASH_VISION_STATIC_FRAME, the
        # photo-on-a-desk pattern) replaces the photon source only —
        # detection, recognition, and reporting stay the real pipeline.
        if self._camera is None:
            self._camera = StaticFrameCamera.from_env()

        # Desktop notifications (decisions.md #74): strictly opt-in, own
        # cooldown, honest delivery record. The notifier is built lazily
        # (guardian's pattern) and only ever when the user enabled it.
        # Initialized BEFORE the config store — _apply_stored_config runs
        # below and reads these as .get() defaults.
        self._notify_enabled_flag = False
        self._notify_cooldown_s = NOTIFY_COOLDOWN_S
        self._notifier: Any = None
        self._last_toast: Optional[dict[str, Any]] = None
        self._last_toast_time = 0.0

        # User configuration (decisions.md #73): persisted JSON, applied at
        # boot so the watcher survives restarts with its configured shape.
        # Injectable store_path keeps tests hermetic.
        self._config_store = WatcherConfigStore(store_path)
        self._apply_stored_config()

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._consecutive_failures = 0
        self._cycles = 0
        self._last_emitted: dict[str, float] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=EVENT_HISTORY_MAX)
        self._persons_seen: dict[str, dict[str, Any]] = {}
        self._last_cycle: Optional[dict[str, Any]] = None
        self._events_total = 0

    # ── user configuration (validated + persisted + live-applied) ────

    def _apply_stored_config(self) -> None:
        cfg = self._config_store.load()
        if cfg:
            self._apply_config(cfg, persist=False)

    @staticmethod
    def _validate_config_change(
        current: dict[str, Any], updates: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        """Validate a partial update against the current config.

        Returns (validated_full_config, errors). A changed camera_id that
        collides with another interval/cooldown change is reported, not
        silently applied — a camera swap mid-config is exactly when a user
        needs to be told.
        """
        errors: list[str] = []
        merged = dict(current)
        for key, value in updates.items():
            if key not in (
                "interval_seconds",
                "repeat_cooldown_s",
                "camera_id",
                "notify_known_persons",
                "notify_cooldown_s",
            ):
                errors.append(f"unknown setting: {key}")
                continue
            if key == "camera_id":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append("camera_id must be an integer")
                    continue
                if not (0 <= value <= MAX_CAMERA_ID):
                    errors.append(f"camera_id must be between 0 and {MAX_CAMERA_ID}")
                    continue
            elif key == "notify_known_persons":
                # A bool is a bool — "yes", 1, and 0 are all rejected:
                # a notification preference stored from a truthy string
                # would be a config lie.
                if not isinstance(value, bool):
                    errors.append("notify_known_persons must be true or false")
                    continue
            else:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"{key} must be a number")
                    continue
                if key == "interval_seconds" and value < MIN_INTERVAL_S:
                    errors.append(
                        f"interval_seconds must be ≥ {MIN_INTERVAL_S} "
                        "(below this the camera is polled faster than it can respond)"
                    )
                    continue
                if key in ("repeat_cooldown_s", "notify_cooldown_s") and value < MIN_COOLDOWN_S:
                    errors.append(f"{key} must be ≥ {MIN_COOLDOWN_S}")
                    continue
            merged[key] = value
        # All-or-nothing honesty: when a multi-field update partially
        # fails, say explicitly that NOTHING applied — otherwise a user
        # changing (camera_id, interval) could believe both landed.
        if errors and "camera_id" in updates and (
            "interval_seconds" in updates
            or "repeat_cooldown_s" in updates
            or "notify_known_persons" in updates
            or "notify_cooldown_s" in updates
        ):
            camera_ok = not any(e.startswith("camera_id") for e in errors)
            other_failed = any(
                not e.startswith("camera_id") for e in errors
            )
            if camera_ok and other_failed:
                errors.append(
                    "note: camera_id was valid but other fields failed — "
                    "nothing is applied (updates are all-or-nothing)"
                )
        return merged, errors

    def _apply_config(
        self, cfg: dict[str, Any], persist: bool = True
    ) -> None:
        """Apply a validated full config to the live watcher.

        Thread-safe against the loop: floats are read atomically by the
        cycle code, and camera_id is only used at capture time — a cycle
        in flight uses one or the other, never a torn mix.
        """
        self._interval = max(MIN_INTERVAL_S, float(cfg["interval_seconds"]))
        self._cooldown_s = max(MIN_COOLDOWN_S, float(cfg["repeat_cooldown_s"]))
        self._camera_id = int(cfg["camera_id"])
        # New keys may be absent in a pre-#74 config file: .get() falls
        # back to the in-memory default instead of raising at boot.
        self._notify_enabled_flag = bool(
            cfg.get("notify_known_persons", self._notify_enabled_flag)
        )
        self._notify_cooldown_s = max(
            MIN_COOLDOWN_S,
            float(cfg.get("notify_cooldown_s", self._notify_cooldown_s)),
        )
        if persist:
            self._config_store.save(self.get_config())

    # ── lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        try:
            while True:
                started = time.monotonic()
                try:
                    await self.run_cycle()
                except Exception:
                    logger.exception("VisionWatcher cycle failed")
                # Failure backoff: consecutive blind cycles stretch the
                # interval (a dead camera is not polled 120×/hour).
                delay = self._current_interval()
                elapsed = time.monotonic() - started
                # Floor is tiny (not 1s) so tests can run the real loop fast.
                await asyncio.sleep(max(0.05, delay - elapsed))
        except asyncio.CancelledError:
            pass

    def _current_interval(self) -> float:
        if self._consecutive_failures <= 0:
            return self._interval
        factor = min(2.0 ** self._consecutive_failures, FAILURE_BACKOFF_MAX)
        return self._interval * factor

    def configure(
        self,
        interval_seconds: Optional[float] = None,
        repeat_cooldown_s: Optional[float] = None,
        camera_id: Optional[int] = None,
        notify_known_persons: Optional[bool] = None,
        notify_cooldown_s: Optional[float] = None,
    ) -> dict[str, Any]:
        """Update the live watcher's knobs; persist on success.

        All-or-nothing: an invalid field means nothing changes and the
        errors come back named. Valid values apply immediately — the next
        cycle uses the new interval/cooldown/camera without a restart.
        """
        updates: dict[str, Any] = {}
        if interval_seconds is not None:
            updates["interval_seconds"] = interval_seconds
        if repeat_cooldown_s is not None:
            updates["repeat_cooldown_s"] = repeat_cooldown_s
        if camera_id is not None:
            updates["camera_id"] = camera_id
        if notify_known_persons is not None:
            updates["notify_known_persons"] = notify_known_persons
        if notify_cooldown_s is not None:
            updates["notify_cooldown_s"] = notify_cooldown_s
        if not updates:
            return {"ok": False, "errors": ["no settings provided"], "applied": {}}
        merged, errors = self._validate_config_change(self.get_config(), updates)
        if errors:
            return {"ok": False, "errors": errors, "applied": {}}
        self._apply_config(merged, persist=True)
        return {"ok": True, "errors": [], "applied": self.get_config()}

    def get_config(self) -> dict[str, Any]:
        return {
            "interval_seconds": self._interval,
            "repeat_cooldown_s": self._cooldown_s,
            "camera_id": self._camera_id,
            "notify_known_persons": self._notify_enabled_flag,
            "notify_cooldown_s": self._notify_cooldown_s,
        }

    # ── one cycle ────────────────────────────────────────────────────

    async def run_cycle(self) -> dict[str, Any]:
        """One capture → analyze → recognize → report pass.

        Never raises: a broken camera or missing models are reported
        states, not exceptions.
        """
        started = time.perf_counter()
        self._cycles += 1
        events: list[dict[str, Any]] = []

        cap = await self._capture()
        analyze_reason = ""
        persons: list[dict[str, Any]] = []
        faces_n = 0
        objects: list[dict[str, Any]] = []
        ok = False

        if not cap.ok:
            self._consecutive_failures += 1
            events.append(
                await self._emit(
                    "camera_unavailable",
                    f"Cannot see: {cap.error}",
                    {"error": cap.error, "hint": cap.hint or ""},
                    key="camera",
                )
            )
        else:
            result = await self._analyze(cap.frame)
            if result is None:
                self._consecutive_failures += 1
                analyze_reason = "frame could not be decoded"
                events.append(
                    await self._emit(
                        "watch_degraded",
                        f"Cannot analyze: {analyze_reason}",
                        {"reason": analyze_reason},
                        key="decode",
                    )
                )
            elif result.backend == "none":
                self._consecutive_failures += 1
                analyze_reason = result.reason
                events.append(
                    await self._emit(
                        "watch_degraded",
                        f"Cannot analyze: {result.reason}",
                        {"reason": result.reason},
                        key="models",
                    )
                )
            else:
                ok = True
                if self._consecutive_failures > 0:
                    self._consecutive_failures = 0
                    events.append(
                        await self._emit(
                            "watch_recovered",
                            "Camera watch recovered: capture and analysis are working again",
                            {},
                            key="recovered",
                        )
                    )
                faces = result.faces
                faces_n = len(faces)
                persons = list(result.persons)
                objects = [o.to_dict() for o in result.objects]

                if persons:
                    for p in persons:
                        events.append(
                            await self._emit_person(p)
                        )
                    unknown = [
                        f for f in faces
                        if f.get("match") is None
                        and f.get("match_status") == "unknown person"
                    ]
                    if unknown:
                        events.append(
                            await self._emit(
                                "unknown_person",
                                "A face on camera did not match anyone enrolled "
                                f"({len(unknown)} unrecognized face"
                                f"{'s' if len(unknown) != 1 else ''}; "
                                "no identity is being guessed)",
                                {"unrecognized": len(unknown)},
                                key="unknown",
                            )
                        )
                elif faces_n:
                    status = faces[0].get("match_status", "")
                    if status == "no persons enrolled":
                        events.append(
                            await self._emit(
                                "unknown_person",
                                "Face on camera but no one is enrolled yet — "
                                "enroll via POST /vision/camera/enroll to be recognized",
                                {"faces": faces_n},
                                key="unknown",
                            )
                        )
                    else:
                        events.append(
                            await self._emit(
                                "unknown_person",
                                "A face on camera did not match anyone enrolled "
                                "(no identity is being guessed)",
                                {"faces": faces_n},
                                key="unknown",
                            )
                        )
                elif objects:
                    summary = ", ".join(
                        f"{o['name']} ({o['confidence']:.2f})" for o in objects[:5]
                    )
                    events.append(
                        await self._emit(
                            "scene",
                            f"Scene: {summary}" + ("…" if len(objects) > 5 else ""),
                            {"objects": objects[:10]},
                            key="scene",
                        )
                    )
                # faces and objects both empty → an honest empty scene:
                # recorded in the cycle, reported as an event only rarely
                # (covered by the same scene cooldown via no emission).

        cycle = {
            "at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "ok": ok,
            "capture_error": None if cap.ok else cap.error,
            "analyze_reason": analyze_reason,
            "faces": faces_n,
            "objects": len(objects),
            "persons": [p["name"] for p in persons],
            "events": [e for e in events if e is not None],
            "consecutive_failures": self._consecutive_failures,
        }
        self._last_cycle = cycle
        return cycle

    # ── seams (lazy singletons; injectable for tests) ────────────────

    async def _capture(self):
        if self._camera is None:
            from dash_backend.vision.camera_vision import get_camera_vision

            self._camera = get_camera_vision()
        return await self._camera.capture_result(self._camera_id)

    async def _analyze(self, frame: bytes):
        """Decode + analyze off the event loop (ONNX inference is CPU work).

        Returns None for an undecodable frame; the VisionResult carries
        backend="none" + reason when models are unavailable.
        """
        from dash_backend.vision import recognition

        def _work() -> Any:
            rgb = recognition.decode_to_rgb_array(frame)
            if rgb is None:
                return None
            recognizer = self._recognizer
            if recognizer is None:
                recognizer = recognition.get_face_service()
            detector = self._detector
            if detector is None:
                try:
                    detector = recognition.get_object_detector()
                except Exception:
                    detector = None
            return recognizer.analyze_frame(rgb, include_objects=detector)

        return await asyncio.to_thread(_work)

    # ── reporting ────────────────────────────────────────────────────

    async def _emit_person(self, match: dict[str, Any]) -> Optional[dict[str, Any]]:
        pid = str(match.get("person_id", "?"))
        name = str(match.get("name", pid))
        seen = self._persons_seen.setdefault(
            name, {"person_id": pid, "count": 0, "last_seen": None}
        )
        seen["count"] += 1
        seen["last_seen"] = datetime.now(timezone.utc).isoformat()
        sim = match.get("similarity")
        sim_s = f" (similarity {sim})" if sim is not None else ""

        # Per-person notify preference (decisions.md #73): an opted-out
        # person is still seen, counted, and recorded in the cycle — they
        # are just not reported to brain/bus/audit. Cooldown state is
        # untouched so opting back in starts a fresh bounded report.
        if not self._person_notify_flag(pid):
            return None

        return await self._emit(
            "person_seen",
            f"Recognized {name} on camera{sim_s} — "
            f"seen {seen['count']}x this session",
            {"person_id": pid, "name": name, "similarity": sim, "box": match.get("box")},
            key=f"person:{pid}",
        )

    async def _emit(
        self, kind: str, message: str, detail: dict[str, Any], key: str
    ) -> Optional[dict[str, Any]]:
        """Report one event through brain + bus + audit, rate-limited per key.

        Returns the delivered record (None when suppressed by cooldown —
        the cycle history still says the scene was seen; it just is not
        repeated to the brain every 30 seconds).
        """
        now = time.time()
        if now - self._last_emitted.get(key, 0.0) < self._cooldown_s:
            return None
        self._last_emitted[key] = now

        delivered = {"brain": False, "bus": False, "audit": False}

        # 0. Per-person preference: an opted-out person is seen and counted
        #    (the cycle record above proves it) but never reported onward.
        #    Checked here so _emit_person alone can't be outsmarted by a
        #    future caller path (decisions.md #73).
        if kind == "person_seen" and not self._person_notify_flag(
            str(detail.get("person_id", ""))
        ):
            return None

        # 1. The brain: the observation enters DASH's working memory, the
        #    same context he reasons from when planning. This is the
        #    "reports through the brain" contract.
        try:
            brain = self._brain
            if brain is None:
                from dash_backend.autonomous.agent_core import get_agent_core

                brain = get_agent_core()
            brain.add_observation(
                {
                    "source": "vision_watcher",
                    "kind": kind,
                    "message": message,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            delivered["brain"] = True
        except Exception:
            logger.debug("VisionWatcher: brain delivery failed", exc_info=True)

        # 2. The event bus: workflows can react (e.g. "on person_seen → …").
        try:
            bus = self._bus
            if bus is None:
                from dash_backend.events.event_bus import get_event_bus

                bus = get_event_bus()
            await bus.publish_sync(
                topic=f"vision.{kind}",
                data={"message": message, **detail},
                source="vision_watcher",
            )
            delivered["bus"] = True
        except Exception:
            logger.debug("VisionWatcher: bus delivery failed", exc_info=True)

        # 3. The audit log: the honest record precedes any use of it.
        try:
            from dash_backend.services.audit_logs import get_audit_service

            get_audit_service().log(
                event_type="VISION_WATCH",
                action=kind,
                status="INFO",
                details={"message": message, **detail},
            )
            delivered["audit"] = True
        except Exception:
            logger.debug("VisionWatcher: audit entry failed", exc_info=True)

        # 4. Desktop toast — strictly opt-in (decisions.md #74), and only
        #    for toast-worthy kinds. The `toast` key appears in `delivered`
        #    ONLY when the channel was attempted: absent means the user
        #    never enabled it, never "tried and silently failed".
        if kind in TOAST_EVENT_KINDS and self._notify_enabled_flag:
            toast = await self._notify_desktop(message)
            delivered["toast"] = toast.get("status") == "ok"

        self._events_total += 1
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "message": message,
            "detail": detail,
            "delivered": delivered,
        }
        self._events.append(entry)
        return entry

    # ── desktop notifications (guardian's notifier pattern) ──────────

    async def _notify_desktop(self, message: str) -> dict[str, Any]:
        """One desktop toast, rate-limited on its own clock.

        Guardian's pattern, reused: the NotificationService is constructed
        lazily (and only when notifications are enabled), failures come
        back as honest {"status": "skipped", "reason"} records instead of
        exceptions, and the attempt — success or failure — is stamped so a
        broken notifier retries at most once per notify_cooldown_s.
        """
        now = time.time()
        if now - self._last_toast_time < self._notify_cooldown_s:
            record = {"status": "skipped", "reason": "notify cooldown active"}
            self._last_toast = {
                "at": datetime.now(timezone.utc).isoformat(),
                **record,
            }
            return record
        # Stamp BEFORE dispatching: a failing toast path must not be
        # retried every cycle (a broken notifier is not polled into spam).
        self._last_toast_time = now
        if self._notifier is None:
            try:
                from dash_backend.services.notifications import NotificationService

                self._notifier = NotificationService()
            except Exception as exc:
                record = {"status": "skipped", "reason": f"notifier unavailable: {exc}"}
                self._last_toast = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    **record,
                }
                return record
        try:
            result = await self._notifier.show(
                title="DASH Vision",
                message=str(message)[:200],
                duration=5,
            )
        except Exception as exc:
            record = {"status": "skipped", "reason": str(exc)}
            self._last_toast = {
                "at": datetime.now(timezone.utc).isoformat(),
                **record,
            }
            return record
        record = {
            "status": "ok",
            "mechanism": str(result.get("mechanism", "")) if isinstance(result, dict) else "",
        }
        self._last_toast = {
            "at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "message": str(message)[:100],
        }
        return record

    # ── observability ────────────────────────────────────────────────

    def _person_notify_flag(self, person_id: str) -> bool:
        """Per-person notify preference; unknown persons notify (fail open)."""
        try:
            if self._recognizer is not None and hasattr(
                self._recognizer, "person_notify_flag"
            ):
                return bool(self._recognizer.person_notify_flag(person_id))
            from dash_backend.vision.recognition import get_face_service

            return bool(get_face_service().person_notify_flag(person_id))
        except Exception:
            logger.debug(
                "notify flag lookup failed — failing open (notify)", exc_info=True
            )
            return True

    def set_person_notify(self, person_id: str, notify: bool) -> dict[str, Any]:
        """Set one person's notify preference (watcher-facing convenience
        used by the API route; the store is the source of truth)."""
        try:
            if self._recognizer is not None and hasattr(
                self._recognizer, "set_person_notify"
            ):
                ok = bool(self._recognizer.set_person_notify(person_id, notify))
            else:
                from dash_backend.vision.recognition import get_face_service

                ok = bool(get_face_service().set_person_notify(person_id, notify))
        except Exception as exc:
            return {"ok": False, "reason": f"preference write failed: {exc}"}
        if not ok:
            return {"ok": False, "reason": "person not found"}
        return {"ok": True, "person_id": person_id, "notify": bool(notify)}

    # ── observability ────────────────────────────────────────────────

    async def scan_now(self) -> dict[str, Any]:
        """Manual single cycle (route + tests); independent of the loop."""
        return await self.run_cycle()

    def get_status(self) -> dict[str, Any]:
        return {
            "available": True,
            "running": self.running,
            "interval_seconds": self._interval,
            "current_interval_seconds": round(self._current_interval(), 1),
            "cooldown_seconds": self._cooldown_s,
            "camera_id": self._camera_id,
            "notify_known_persons": self._notify_enabled_flag,
            "notify_cooldown_s": self._notify_cooldown_s,
            "last_toast": self._last_toast,
            "config_persisted": self._config_store.path,
            "cycles": self._cycles,
            "events_total": self._events_total,
            "consecutive_failures": self._consecutive_failures,
            "persons_seen": [
                {"name": name, **info} for name, info in self._persons_seen.items()
            ],
            "last_cycle": self._last_cycle,
            "recent_events": list(self._events)[-10:],
        }


_watcher: Optional[VisionWatcher] = None


def _config_path() -> Path:
    """Watcher config file location. Override with DASH_WATCHER_CONFIG for
    tests; default lives beside the other per-user state under
    LOCALAPPDATA/DASH (same convention as workflow_state.json)."""
    override = os.environ.get("DASH_WATCHER_CONFIG")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DASH" / "watcher_config.json"


class WatcherConfigStore:
    """Persisted watcher configuration (JSON, versioned, corrupt-safe).

    A corrupt or version-mismatched file is reported (``last_error``) and
    ignored — defaults apply, and the file is rewritten on the next
    successful save. The watcher never boots with garbage values.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path: Path = Path(path) if path else _config_path()
        self.last_error: Optional[str] = None

    # Per-key type contract for the persisted file (decisions.md #73/#74):
    # floats accept int|float (never bool), int accepts int (never bool),
    # bool accepts ONLY bool — a truthy string must never become a flag.
    _KEY_TYPES: dict[str, type] = {
        "interval_seconds": float,
        "repeat_cooldown_s": float,
        "notify_cooldown_s": float,
        "camera_id": int,
        "notify_known_persons": bool,
    }

    def load(self) -> dict[str, Any]:
        self.last_error = None
        try:
            if not self.path.exists():
                return {}
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.last_error = "config file unreadable — defaults in use"
            logger.warning("Watcher config unreadable; defaults apply", exc_info=True)
            return {}
        if not isinstance(data, dict) or data.get("version") != WATCHER_CONFIG_VERSION:
            self.last_error = "config version mismatch — defaults in use"
            return {}
        cfg = data.get("watcher", {})
        if not isinstance(cfg, dict):
            self.last_error = "config watcher block invalid — defaults in use"
            return {}
        out: dict[str, Any] = {}
        for key, want in self._KEY_TYPES.items():
            if key not in cfg:
                continue
            value = cfg[key]
            if want is bool:
                if isinstance(value, bool):
                    out[key] = value
            elif want is int:
                if isinstance(value, int) and not isinstance(value, bool):
                    out[key] = value
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                out[key] = value
        return out

    def save(self, cfg: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    {"version": WATCHER_CONFIG_VERSION, "watcher": cfg}, indent=2
                ),
                encoding="utf-8",
            )
            self.last_error = None
        except Exception:
            self.last_error = "config save failed — running with in-memory values"
            logger.exception("Watcher config save failed")


def get_vision_watcher() -> VisionWatcher:
    global _watcher
    if _watcher is None:
        _watcher = VisionWatcher()
    return _watcher


# ── Static frame source (demo/no-camera testing) ────────────────────────

class StaticFrameCamera:
    """A camera object that always captures the same encoded image file.

    Purpose: exercise the watcher's REAL pipeline (capture → decode →
    YuNet detect → SFace recognize → emit → bus) on machines with no
    camera and no fake recognition objects — the only substituted thing
    is the photon source, exactly like pointing a webcam at a photograph.
    Env-gated (``DASH_VISION_STATIC_FRAME`` = path to an image file) so it
    can never activate silently in production.
    """

    _cache: dict[str, Optional[bytes]] = {}

    @classmethod
    def from_env(cls) -> Optional["StaticFrameCamera"]:
        raw = os.environ.get("DASH_VISION_STATIC_FRAME", "").strip()
        if not raw:
            return None
        p = Path(raw)
        if not p.is_file():
            logger.error(
                "DASH_VISION_STATIC_FRAME=%s is set but not a readable file — "
                "watcher falls back to the real camera path",
                raw,
            )
            return None
        return cls(p)

    def __init__(self, image_path: Path) -> None:
        self._path = Path(image_path)

    def _frame(self) -> Optional[bytes]:
        path_s = str(self._path)
        if path_s not in StaticFrameCamera._cache:
            try:
                StaticFrameCamera._cache[path_s] = self._path.read_bytes()
            except OSError:
                StaticFrameCamera._cache[path_s] = None
        return StaticFrameCamera._cache[path_s]

    async def capture_result(self, camera_id: int = 0):
        from dash_backend.vision.camera_vision import CaptureResult

        frame = self._frame()
        if frame is None:
            return CaptureResult(
                frame=None,
                error=f"static frame unreadable: {self._path}",
                hint="fix DASH_VISION_STATIC_FRAME or unset it",
            )
        return CaptureResult(frame=frame)

    def release(self) -> None:  # CameraVision surface parity
        pass
