"""Camera pipeline tests (docs/ROADMAP.md Phase 1): capture → decode →
analyze → enroll, end to end, all hermetic.

CameraVision is exercised with a fake cv2 module injected into sys.modules
— no real camera, no OpenCV install required. The fake mimics exactly the
surface CameraVision uses (VideoCapture / isOpened / read / release /
imencode), so every failure cause in the honesty contract gets its own
test: no OpenCV, device absent/busy, device that opens but returns no
frame, encode failure, and success (verified down to jpeg bytes that
decode back to a real frame).

Route tests run through the real app with a stub camera patched into the
singleton, covering: 503 with the named cause + hint, 422 on undecodable
frames, 409 with the missing-model reason on enroll, and a full
frame→detection happy path using the same injected fake ONNX sessions as
test_vision_recognition.py.
"""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pytest

from dash_backend.vision import recognition as rec
from dash_backend.vision.camera_vision import (
    CaptureResult,
    CameraVision,
    get_camera_vision,
)
from tests.test_vision_recognition import (  # reuse the fake ONNX sessions
    FakeSession,
    FakeYOLOSession,
    FakeYuNetSession,
    _make_image,
    _png_bytes,
)

try:
    from PIL import Image

    _PIL = True
except ImportError:  # pragma: no cover
    _PIL = False

requires_pil = pytest.mark.skipif(not _PIL, reason="Pillow not installed")


# ── Fake cv2 machinery ────────────────────────────────────────────────────


class _JpegBuf:
    """Stands in for cv2.imencode's returned ndarray (needs .tobytes())."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def tobytes(self) -> bytes:
        return self._data


def _install_fake_cv2(
    monkeypatch: pytest.MonkeyPatch,
    *,
    opens: bool = True,
    read_returns: bool = True,
    frame: Optional[np.ndarray] = None,
    fail_encode: bool = False,
    constructor_raises: Optional[str] = None,
) -> dict[str, Any]:
    """Install a fake cv2 in sys.modules; return call-recording dict."""
    frame = frame if frame is not None else np.zeros((48, 64, 3), dtype=np.uint8)
    calls: dict[str, Any] = {"encode": 0, "released": 0, "reads": 0}

    class FakeVideoCapture:
        def __init__(self, index: int = 0) -> None:
            if constructor_raises:
                raise RuntimeError(constructor_raises)
            self.index = index
            self._opened = opens
            self._released = False

        def isOpened(self) -> bool:
            return self._opened

        def read(self):
            calls["reads"] += 1
            if read_returns:
                return True, frame
            return False, None

        def release(self) -> None:
            calls["released"] += 1
            self._released = True

    def imencode(ext: str, arr: np.ndarray):
        calls["encode"] += 1
        if fail_encode:
            return False, None
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="JPEG")
        return True, _JpegBuf(buf.getvalue())

    fake = types.ModuleType("cv2")
    fake.VideoCapture = FakeVideoCapture  # type: ignore[attr-defined]
    fake.imencode = imencode  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cv2", fake)
    return calls


# ── CameraVision: every failure cause, named ──────────────────────────────


async def test_capture_without_opencv_names_the_cause(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "cv2", None)  # import cv2 → ImportError
    result = await CameraVision().capture_result(0)
    assert result.ok is False and result.frame is None
    assert "opencv not installed" in result.error
    assert "pip install opencv-python" in result.hint


async def test_capture_device_absent_is_named(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, opens=False)
    result = await CameraVision().capture_result(0)
    assert result.ok is False
    assert "no camera available" in result.error
    assert "connect a camera" in result.hint


async def test_capture_device_returns_no_frame_is_named(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, opens=True, read_returns=False)
    result = await CameraVision().capture_result(0)
    assert result.ok is False
    assert "opened but returned no frame" in result.error
    assert "busy" in result.hint


async def test_capture_encode_failure_is_named(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, fail_encode=True)
    result = await CameraVision().capture_result(0)
    assert result.ok is False
    assert "encoded" in result.error


async def test_capture_device_exception_is_contained(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, constructor_raises="device wedged")
    result = await CameraVision().capture_result(0)
    assert result.ok is False
    assert "capture failed" in result.error and "device wedged" in result.error


@requires_pil
async def test_capture_success_returns_decodable_jpeg_and_releases(
    monkeypatch,
) -> None:
    calls = _install_fake_cv2(monkeypatch)
    result = await CameraVision().capture_result(2)
    assert result.ok is True
    rgb = rec.decode_to_rgb_array(result.frame)
    assert rgb is not None and rgb.shape == (48, 64, 3)
    assert calls["released"] == 1  # device freed for the next caller

    # Legacy boolean shim shares the same path.
    legacy = await CameraVision().capture(2)
    assert legacy == result.frame


def test_capture_result_dataclass_and_singleton() -> None:
    ok = CaptureResult(frame=b"x")
    assert ok.ok is True
    bad = CaptureResult(frame=None, error="e", hint="h")
    assert bad.ok is False
    assert get_camera_vision() is get_camera_vision()


# ── Routes through the real app ───────────────────────────────────────────


class StubCamera:
    """Replaces the camera singleton with scripted outcomes."""

    def __init__(self, result: CaptureResult) -> None:
        self._result = result
        self.calls = 0

    async def capture_result(self, camera_id: int = 0) -> CaptureResult:
        self.calls += 1
        return self._result


@pytest.fixture()
def fresh_singletons(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolated model dir + reset recognition/camera singletons."""
    monkeypatch.setenv("DASH_VISION_MODELS", str(tmp_path / "models"))
    monkeypatch.setattr(rec, "_object_detector", None)
    monkeypatch.setattr(rec, "_face_service", None)
    yield


def _stub_camera(monkeypatch: pytest.MonkeyPatch, result: CaptureResult) -> StubCamera:
    import dash_backend.vision.camera_vision as cvmod

    stub = StubCamera(result)
    monkeypatch.setattr(cvmod, "_camera_vision", stub)
    return stub


async def test_camera_analyze_reports_capture_failure_verbatim(
    client, fresh_singletons, monkeypatch
) -> None:
    _stub_camera(
        monkeypatch,
        CaptureResult(
            frame=None,
            error="no camera available (device absent or busy)",
            hint="connect a camera or free it from other apps",
        ),
    )
    r = await client.post("/api/v1/vision/camera/analyze")
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "no camera available" in detail
    assert "connect a camera" in detail  # the fix hint travels to the user


async def test_camera_analyze_undecodable_frame_is_422(
    client, fresh_singletons, monkeypatch
) -> None:
    _stub_camera(monkeypatch, CaptureResult(frame=b"not-a-jpeg"))
    r = await client.post("/api/v1/vision/camera/analyze")
    assert r.status_code == 422
    assert "captured frame" in r.json()["detail"]


@requires_pil
async def test_camera_analyze_end_to_end_with_injected_sessions(
    client, fresh_singletons, monkeypatch
) -> None:
    """Full pipeline: camera frame → decode → faces + objects, no models
    on disk needed — the fake ONNX sessions are injected into the real
    singletons the routes use."""
    jpeg = _png_bytes(_make_image())  # decode path accepts any Pillow format
    _stub_camera(monkeypatch, CaptureResult(frame=jpeg))

    svc = rec.get_face_service()
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([np.full((1, 128), 0.5, dtype=np.float32)]),
    )
    det = rec.get_object_detector()
    det._inject_session(
        FakeYOLOSession([(0, 0.9, 320.0, 320.0, 80.0, 100.0)]),
        input_name="images",
        input_hw=(640, 640),
    )

    r = await client.post("/api/v1/vision/camera/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "onnx"
    assert len(body["faces"]) == 1 and len(body["objects"]) == 1
    assert body["objects"][0]["name"] == "person"


@requires_pil
async def test_camera_enroll_route_full_path(
    client, fresh_singletons, monkeypatch
) -> None:
    jpeg = _png_bytes(_make_image())
    stub = _stub_camera(monkeypatch, CaptureResult(frame=jpeg))

    # 1) Missing name → 422 before any camera access.
    r = await client.post("/api/v1/vision/camera/enroll")
    assert r.status_code == 422

    # 2) Models missing → enroll says exactly which model to fetch.
    r = await client.post("/api/v1/vision/camera/enroll", params={"name": "Alice"})
    assert r.status_code == 409
    assert "yunet" in r.json()["detail"]

    # 3) Models "present" (injected fakes) → enrolled from the camera frame.
    svc = rec.get_face_service()
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([np.full((1, 128), 0.5, dtype=np.float32)]),
    )
    r = await client.post("/api/v1/vision/camera/enroll", params={"name": "Alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["name"] == "Alice" and body["samples"] == 1
    assert stub.calls == 2  # only the two attempts above touched the camera


async def test_camera_enroll_capture_failure_is_503(
    client, fresh_singletons, monkeypatch
) -> None:
    _stub_camera(
        monkeypatch,
        CaptureResult(
            frame=None,
            error="opencv not installed",
            hint="pip install opencv-python, then restart DASH",
        ),
    )
    r = await client.post(
        "/api/v1/vision/camera/enroll", params={"name": "Alice"}
    )
    assert r.status_code == 503
    assert "opencv not installed" in r.json()["detail"]
