"""Real vision recognition tests (docs/ROADMAP.md Phase 1 / decisions.md #55).

Everything is hermetic: fake ONNX sessions are injected, so no model files,
no camera, no downloads. Geometry (letterbox round-trip, coordinate
un-mapping, NMS) and matching math (cosine similarity, threshold) are
exercised against synthetic frames.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from dash_backend.vision import recognition as rec


# ── Fixtures / helpers ────────────────────────────────────────────────────


class FakeSession:
    """Stands in for an ort session: returns canned outputs for any input."""

    def __init__(self, outputs: list[np.ndarray], input_name: str = "input.1"):
        self._outputs = outputs
        self.input_name = input_name

    def run(self, output_names: list[str], feed: dict[str, Any]) -> list[Any]:
        assert feed  # a real feed dict arrives
        return self._outputs


class FakeYOLOSession(FakeSession):
    """YOLO-style output: (1, 4+N, M) with xywh rows + per-class scores."""

    def __init__(self, dets: list[tuple[int, float, float, float, float, float]], num_classes: int = 80):
        # dets: (class_id, conf, cx, cy, w, h) in input-space coords
        rows = np.zeros((4 + num_classes, max(1, len(dets))), dtype=np.float32)
        for i, (cid, conf, cx, cy, w, h) in enumerate(dets):
            rows[cid + 4, i] = conf
            rows[0, i], rows[1, i] = cx, cy
            rows[2, i], rows[3, i] = w, h
        super().__init__([rows[None]], input_name="images")


class FakeYuNetSession:
    """Fake FACE DETECTOR at the decoded-face seam: detect_faces(rgb) ->
    [{"box", "confidence"}]. This matches what _FaceDetector (the real
    cv2.FaceDetectorYN adapter) returns, so tests exercise the exact
    contract the production code consumes.
    """

    def __init__(self, faces: list[tuple[int, int, int, int, float]]):
        self._faces = faces
        self.input_name = "input"  # kept for diagnostics

    def detect_faces(self, rgb):
        w = rgb.shape[1]
        out = []
        for (x, y, fw, fh, conf) in self._faces:
            out.append(
                {
                    "box": [x, y, min(x + fw, w), y + fh],
                    "confidence": conf,
                    "landmarks": [(x + fw // 2, y + fh // 2)],
                }
            )
        return out


def _make_image(w: int = 320, h: int = 240, fill: int = 100) -> np.ndarray:
    return np.full((h, w, 3), fill, dtype=np.uint8)


def _png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


try:
    from PIL import Image  # noqa: E402  (needed by helpers above)

    _PIL = True
except ImportError:  # pragma: no cover
    _PIL = False

requires_pil = pytest.mark.skipif(not _PIL, reason="Pillow not installed")


@pytest.fixture()
def models_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    d = tmp_path / "vision_models"
    monkeypatch.setenv("DASH_VISION_MODELS", str(d))
    return d


@pytest.fixture()
def fresh_singletons(models_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset recognition singletons so env overrides are honored."""
    monkeypatch.setattr(rec, "_object_detector", None)
    monkeypatch.setattr(rec, "_face_service", None)
    yield


# ── Decoding ──────────────────────────────────────────────────────────────


@requires_pil
def test_decode_valid_and_invalid_bytes(models_dir: Path, fresh_singletons) -> None:
    rgb = rec.decode_to_rgb_array(_png_bytes(_make_image()))
    assert rgb is not None and rgb.shape == (240, 320, 3)

    assert rec.decode_to_rgb_array(b"not an image") is None
    assert rec.decode_to_rgb_array(b"") is None


# ── NMS ───────────────────────────────────────────────────────────────────


def test_nms_suppresses_overlaps_keeps_distinct() -> None:
    boxes = [
        np.array([0, 0, 10, 10], dtype=np.float32),
        np.array([1, 1, 11, 11], dtype=np.float32),  # overlaps #0
        np.array([100, 100, 120, 120], dtype=np.float32),  # distinct
    ]
    scores = [0.9, 0.8, 0.7]
    keep = rec.nms(boxes, scores, iou_thr=0.5)
    assert keep == [0, 2]


# ── Object detector (injected fake session) ───────────────────────────────


@requires_pil
def test_detector_missing_model_is_honest(models_dir: Path, fresh_singletons) -> None:
    det = rec.ObjectDetectorONNX(model_dir=models_dir)
    assert det.available is False
    reason = det.unavailable_reason
    assert "missing" in reason and "yolov8n.onnx" in reason
    assert "fetch_vision_models" in reason  # tells the user how to fix it

    result = det.detect(_make_image())
    assert result == []


@requires_pil
def test_detect_maps_boxes_back_to_original_coords(models_dir: Path, fresh_singletons) -> None:
    """A face-class detection centered in a 640 letterboxed input must land
    back at the same relative position in the original 320x240 frame."""
    det = rec.ObjectDetectorONNX(model_dir=models_dir)
    # 640x640 input; image 320x240 → gain=2.0, pad_w=0, pad_h=80.
    # Person at original (160,120) center, 40x50 px → 640-space:
    # cx=320, cy=(120*2+80)=320, w=80, h=100.
    det._inject_session(
        FakeYOLOSession([(0, 0.91, 320.0, 320.0, 80.0, 100.0)]),
        input_name="images",
        input_hw=(640, 640),
    )
    detections = det.detect(_make_image())
    assert len(detections) == 1
    d = detections[0]
    assert d.name == "person"
    assert d.backend == "onnx"
    # Un-letterboxed box ≈ centered at (160,120), size 40x50. Tolerance 3px:
    # letterbox padding splits unevenly for even targets (79/81 for 240px),
    # so recovered coords shift by the 1px rounding of the pad split.
    assert d.box[2] - d.box[0] == pytest.approx(40, abs=3)
    assert d.box[3] - d.box[1] == pytest.approx(50, abs=3)
    assert d.box[0] == pytest.approx(140, abs=3)
    assert d.box[1] == pytest.approx(95, abs=3)


@requires_pil
def test_detect_filters_low_confidence_and_applies_nms(models_dir: Path, fresh_singletons) -> None:
    det = rec.ObjectDetectorONNX(model_dir=models_dir)
    det._inject_session(
        FakeYOLOSession(
            [
                (0, 0.9, 320.0, 320.0, 60.0, 60.0),  # kept
                (0, 0.85, 322.0, 322.0, 60.0, 60.0),  # NMS-suppressed
                (5, 0.1, 100.0, 100.0, 60.0, 60.0),  # below threshold
            ]
        ),
        input_name="images",
        input_hw=(640, 640),
    )
    detections = det.detect(_make_image())
    assert len(detections) == 1
    assert detections[0].confidence == pytest.approx(0.9, abs=0.01)


# ── Face service: honesty + enrollment + matching ─────────────────────────


@requires_pil
def test_face_models_missing_reports_reasons(models_dir: Path, fresh_singletons) -> None:
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    assert svc.available is False
    reasons = svc.unavailable_reasons()
    assert "detector" in reasons and "embedder" in reasons
    assert "yunet" in reasons["detector"] and "sface" in reasons["embedder"]

    result = svc.analyze_frame(_make_image())
    assert result.objects == [] and result.faces == []
    assert result.backend == "none"
    assert "missing" in result.reason


@requires_pil
def test_enroll_requires_name_and_face(models_dir: Path, fresh_singletons, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    assert svc.enroll(_make_image(), "  ")["ok"] is False  # no name

    # Inject sessions but return zero faces: enroll must say so honestly.
    svc._inject_sessions(
        FakeYuNetSession([]),  # no detections
        FakeSession([np.zeros((1, 128), dtype=np.float32)]),
    )
    res = svc.enroll(_make_image(), "Alice")
    assert res["ok"] is False
    assert "no face detected" in res["reason"]


@requires_pil
def test_enroll_then_recognize_same_person(models_dir: Path, fresh_singletons, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASH_FACE_MATCH_THRESHOLD", "0.5")
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    fixed_vec = np.full((1, 128), 0.5, dtype=np.float32)
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([fixed_vec]),  # deterministic embedding for every crop
    )
    res = svc.enroll(_make_image(), "Alice")
    assert res["ok"] is True and res["samples"] == 1
    assert svc.list_persons() == [{"person_id": res["person_id"], "name": "Alice", "samples": 1, "notify": True}]

    # Same embedding again → recognized above threshold.
    result = svc.analyze_frame(_make_image())
    assert result.backend == "onnx"
    assert len(result.faces) == 1
    assert result.faces[0]["match"]["name"] == "Alice"
    assert result.faces[0]["match"]["similarity"] == pytest.approx(1.0, abs=0.01)
    assert result.persons and result.persons[0]["name"] == "Alice"

    # A second sample accumulates.
    res2 = svc.enroll(_make_image(), "Alice", person_id=res["person_id"])
    assert res2["samples"] == 2


@requires_pil
def test_unknown_person_is_labeled_not_guessed(models_dir: Path, fresh_singletons, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    # Enroll with vector A...
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([np.full((1, 128), 0.5, dtype=np.float32)]),
    )
    svc.enroll(_make_image(), "Alice")
    # ...then analyze with a truly orthogonal vector B (dot product = 0):
    # A is +0.5 everywhere, so B must sum to zero per element product.
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([np.concatenate([np.full((1, 64), -1.0, dtype=np.float32), np.full((1, 64), 1.0, dtype=np.float32)], axis=1)]),
    )
    result = svc.analyze_frame(_make_image())
    assert result.faces[0]["match"] is None
    assert result.faces[0]["match_status"] == "unknown person"
    assert result.persons == []


@requires_pil
def test_no_persons_enrolled_status_is_explicit(models_dir: Path, fresh_singletons) -> None:
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    svc._inject_sessions(
        FakeYuNetSession([(100, 60, 120, 120, 0.97)]),
        FakeSession([np.full((1, 128), 0.5, dtype=np.float32)]),
    )
    result = svc.analyze_frame(_make_image())
    assert result.faces[0]["match"] is None
    assert result.faces[0]["match_status"] == "no persons enrolled"


def test_remove_person(models_dir: Path, fresh_singletons) -> None:
    svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
    svc._store.add_sample("p1", "Alice", [0.1] * 8)
    assert svc.remove_person("p1") is True
    assert svc.remove_person("p1") is False
    assert svc.list_persons() == []


# ── Model status + persistence ────────────────────────────────────────────


def test_model_status_reports_each_manifest_entry(models_dir: Path, fresh_singletons) -> None:
    status = rec.model_status()
    files = {m["file"]: m["available"] for m in status["models"]}
    assert set(files) == {"yolov8n.onnx", "face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx"}
    assert not status["all_available"]
    # Create one and re-check.
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "yolov8n.onnx").write_bytes(b"x" * 100)
    status2 = rec.model_status()
    by_file = {m["file"]: m for m in status2["models"]}
    assert by_file["yolov8n.onnx"]["available"] is True
    assert by_file["face_detection_yunet_2023mar.onnx"]["available"] is False


@requires_pil
def test_face_store_persists_across_restart(models_dir: Path, fresh_singletons) -> None:
    store_path = models_dir / "faces.json"
    svc1 = rec.FaceRecognitionService(model_dir=models_dir, store_path=store_path)
    svc1._store.add_sample("p1", "Alice", [0.25] * 16)
    svc2 = rec.FaceRecognitionService(model_dir=models_dir, store_path=store_path)
    persons = svc2.list_persons()
    assert persons == [
        {"person_id": "p1", "name": "Alice", "samples": 1, "notify": True}
    ]


# ── The dishonest legacy path must stay dead ──────────────────────────────


@requires_pil
async def test_legacy_detector_reports_honestly_without_models(models_dir: Path, fresh_singletons) -> None:
    from dash_backend.vision.object_detector import ObjectDetector

    det = ObjectDetector()
    out = await det.detect_objects(b"garbage-not-an-image")
    assert out[0]["backend"] == "none"
    assert "decoded" in out[0]["reason"]

    png = _png_bytes(_make_image())
    out2 = await det.detect_objects(png)
    assert out2[0]["backend"] == "none"
    assert "missing" in out2[0]["reason"]  # models not fetched yet — named, not faked
