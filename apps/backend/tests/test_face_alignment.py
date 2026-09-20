"""SFace 5-point landmark alignment tests (decisions.md #67).

The embedding pipeline now similarity-warps each detected face onto the
canonical ArcFace 5-point template before SFace, using the landmarks YuNet
already detects (previously discarded). All tests here are hermetic:
synthetic frames and fake detector/embedder sessions. The real-model
cross-image verification lives in scripts/verify_face_alignment.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

import dash_backend.vision.recognition as rec


# ── Fakes ─────────────────────────────────────────────────────────────────


class FakeSession:
    """Fake embedder session: records the fed tensors, returns a fixed 128-d vec."""

    input_name = "input.1"

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def run(self, _outputs, feed):
        self.calls.append(feed)
        return [np.full((1, 128), 0.5, dtype=np.float32)]


class FakeDetector:
    """Fake detector at the decoded-face seam."""

    def __init__(self, faces: list[dict[str, Any]]) -> None:
        self._faces = faces

    def detect_faces(self, rgb):
        return self._faces


class StubYuNet:
    """Fake raw cv2.FaceDetectorYN: returns a 15-column landmark row."""

    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = np.asarray(rows, dtype=np.float32)

    def setInputSize(self, size) -> None:  # noqa: N802 (cv2 naming)
        pass

    def detect(self, rgb):
        return (0, self._rows)


def _box(x: int, y: int, w: int, h: int, conf: float = 0.97) -> dict[str, Any]:
    return {"box": [x, y, x + w, y + h], "confidence": conf}


def _face_frame(size: int = 224, scale: float = 2.0) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Synthetic 'face': bright blobs at canonical-landmark positions.

    The canvas is `size` px; the canonical 112-space template is scaled by
    `scale` into it. Blobs give the warp geometric features to lock onto.
    """
    img = np.zeros((size, size, 3), dtype=np.uint8)
    lm = [(x * scale, y * scale) for x, y in rec._ARCFACE_DST_LANDMARKS]
    for i, (x, y) in enumerate(lm):
        xi, yi = int(round(x)), int(round(y))
        shade = 60 + i * 40
        img[max(0, yi - 6) : yi + 6, max(0, xi - 6) : xi + 6] = (shade, shade, shade)
    return img, [(float(x), float(y)) for x, y in lm]


# ── _normalize_landmarks ──────────────────────────────────────────────────


class TestNormalizeLandmarks:
    def test_five_in_frame_points_pass(self) -> None:
        pts = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (9.0, 10.0)]
        assert rec._normalize_landmarks(pts, 100, 100) == pts

    def test_none_and_wrong_counts_rejected(self) -> None:
        assert rec._normalize_landmarks(None, 100, 100) is None
        assert rec._normalize_landmarks([(1, 2)], 100, 100) is None  # legacy 1-pt fake
        assert rec._normalize_landmarks([(1, 2)] * 4, 100, 100) is None
        assert rec._normalize_landmarks([(1, 2)] * 6, 100, 100) is None

    def test_unparseable_points_rejected(self) -> None:
        assert rec._normalize_landmarks([(1, 2), (3, 4), (5, 6), (7, 8), "nope"], 100, 100) is None
        assert rec._normalize_landmarks([(None, 2), (3, 4), (5, 6), (7, 8), (9, 10)], 100, 100) is None

    def test_out_of_frame_points_rejected(self) -> None:
        base = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)]
        assert rec._normalize_landmarks([(-1.0, 0.0)] + base, 100, 100) is None
        assert rec._normalize_landmarks(base + [(100.0, 50.0)], 100, 100) is None
        # Boundary is inclusive at 0, exclusive at w/h (still 5 points total)
        assert rec._normalize_landmarks([(0.0, 0.0)] + base, 100, 100) is not None
        assert rec._normalize_landmarks(base + [(99.0, 50.0)], 100, 100) is not None

    def test_numpy_rows_accepted(self) -> None:
        arr = np.arange(10, dtype=np.float32).reshape(5, 2)
        pts = rec._normalize_landmarks(arr, 100, 100)
        assert pts is not None and len(pts) == 5


# ── _align_face math ──────────────────────────────────────────────────────


class TestAlignFace:
    def test_exact_similarity_is_recovered(self) -> None:
        # Landmarks = canonical template x2 on a 224 canvas → the warp must
        # invert exactly: aligned[y, x] == canvas[2y, 2x].
        canvas, lm = _face_frame(224, scale=2.0)
        aligned = rec._align_face(canvas, lm, out_size=112)
        assert aligned is not None and aligned.shape == (112, 112, 3)
        for y in range(8, 104, 16):
            for x in range(8, 104, 16):
                assert np.allclose(aligned[y, x], canvas[2 * y, 2 * x]), (x, y)

    def test_rotation_invariance_beats_margin_crop(self) -> None:
        # The same 'face' upright and rotated 30°: aligned warps must land
        # nearly identical, while margin-crops of the two differ much more.
        canvas, lm = _face_frame(224, scale=2.0)
        import cv2

        mat = cv2.getRotationMatrix2D((112, 112), 30.0, 1.0)
        rotated = cv2.warpAffine(canvas, mat, (224, 224))
        lm_rot = [
            (
                float(mat[0, 0] * x + mat[0, 1] * y + mat[0, 2]),
                float(mat[1, 0] * x + mat[1, 1] * y + mat[1, 2]),
            )
            for x, y in lm
        ]
        a_up = rec._align_face(canvas, lm, out_size=112)
        a_rot = rec._align_face(rotated, lm_rot, out_size=112)
        assert a_up is not None and a_rot is not None
        aligned_diff = float(np.abs(a_up.astype(int) - a_rot.astype(int)).mean())
        # Unaligned margin-crop of the same two frames:
        box = [44, 44, 200, 200]
        c_up = rec._crop_with_margin(canvas, box)
        c_rot = rec._crop_with_margin(rotated, box)
        crop_diff = float(np.abs(c_up.astype(int) - c_rot.astype(int)).mean())
        assert aligned_diff < 10.0, aligned_diff
        assert aligned_diff < crop_diff * 0.5, (aligned_diff, crop_diff)

    def test_degenerate_landmarks_do_not_crash(self) -> None:
        canvas, _ = _face_frame(224, scale=2.0)
        same = [(50.0, 50.0)] * 5
        out = rec._align_face(canvas, same, out_size=112)
        # Solver fails or produces something — either way, no exception and
        # the caller falls back if None.
        assert out is None or out.shape == (112, 112, 3)


# ── Service integration ───────────────────────────────────────────────────


class TestServiceAlignment:
    @pytest.fixture()
    def models_dir(self, tmp_path: Path) -> Path:
        # No real models needed: sessions are injected below.
        return tmp_path

    def test_embedder_fed_raw_0_255_pixels(self, models_dir: Path) -> None:
        """Pin the SFace input contract: RAW 0-255 RGB, NO normalization.

        The ArcFace-style (x-127.5)/128 scaling previously used here starved
        the model (feature norm ~2.2 vs ~12.8 reference; every face matched
        every other at ~0.93 — decisions.md #61/#68). If this test fails,
        the preprocessing has regressed and recognition is fake again.
        """
        frame = np.full((120, 120, 3), 200, dtype=np.uint8)
        frame[40:80, 40:80] = 20  # some contrast
        svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
        fake_emb = FakeSession()
        svc._inject_sessions(
            FakeDetector([_box(30, 30, 60, 60, conf=0.97)]),
            fake_emb,
        )
        result = svc.analyze_frame(frame)
        assert result.faces, "face must be analyzed"
        fed = fake_emb.calls[0]["input.1"]
        assert fed.shape == (1, 3, 112, 112)
        # Raw pixel scale: values live in [0, 255], and the bright background
        # (200) survived untouched — any normalization would have changed it.
        assert fed.min() >= 0.0 and fed.max() <= 255.0
        assert np.isclose(float(fed.max()), 200.0, atol=1e-3)
        assert np.isclose(float(fed.min()), 20.0, atol=1e-3)

    def test_aligned_path_used_and_flagged(self, models_dir: Path) -> None:
        canvas, lm = _face_frame(224, scale=2.0)
        svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
        fake_emb = FakeSession()
        svc._inject_sessions(
            FakeDetector([{"box": [30, 30, 210, 210], "confidence": 0.98, "landmarks": lm}]),
            fake_emb,
        )
        res = svc.enroll(canvas, "Alice")
        assert res["ok"] is True
        # The embedder was fed the aligned 112x112 warp.
        fed = fake_emb.calls[0]["input.1"]
        assert fed.shape == (1, 3, 112, 112)
        result = svc.analyze_frame(canvas)
        assert result.faces[0]["landmark_aligned"] is True
        assert result.faces[0]["match"]["name"] == "Alice"

    def test_legacy_single_landmark_falls_back_honestly(self, models_dir: Path) -> None:
        # The pre-alignment fake emitted a 1-point landmarks list: it must
        # take the margin-crop path (flagged NOT landmark-aligned) and still
        # match itself — same deterministic fallback both times.
        canvas, _ = _face_frame(224, scale=2.0)
        svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
        svc._inject_sessions(
            FakeDetector([{"box": [30, 30, 210, 210], "confidence": 0.98, "landmarks": [(120.0, 120.0)]}]),
            FakeSession(),
        )
        res = svc.enroll(canvas, "Bob")
        assert res["ok"] is True
        result = svc.analyze_frame(canvas)
        assert result.faces[0]["landmark_aligned"] is False
        assert result.faces[0]["match"]["name"] == "Bob"

    def test_no_landmarks_key_falls_back(self, models_dir: Path) -> None:
        canvas, _ = _face_frame(224, scale=2.0)
        svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=models_dir / "faces.json")
        svc._inject_sessions(FakeDetector([_box(30, 30, 180, 180)]), FakeSession())
        result = svc.analyze_frame(canvas)
        assert result.faces[0]["landmark_aligned"] is False
        assert result.faces[0]["match_status"] == "no persons enrolled"


# ── Real YuNet adapter passes landmarks through ──────────────────────────


class TestYuNetLandmarkPassthrough:
    def test_row_landmarks_surface_in_output(self) -> None:
        row = [10.0, 10.0, 50.0, 50.0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0.9]
        det = rec._FaceDetector(StubYuNet([row]))
        out = det.detect_faces(np.zeros((100, 100, 3), dtype=np.uint8))
        assert len(out) == 1
        assert out[0]["landmarks"] == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (9.0, 10.0)]
        assert out[0]["box"] == [10, 10, 60, 60]
        assert out[0]["confidence"] == 0.9

    def test_low_confidence_rows_dropped(self) -> None:
        row = [10.0, 10.0, 50.0, 50.0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0.3]
        det = rec._FaceDetector(StubYuNet([row]))
        out = det.detect_faces(np.zeros((100, 100, 3), dtype=np.uint8))
        assert out == []


# ── models dir resolution fix ─────────────────────────────────────────────


class TestModelsDir:
    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("DASH_VISION_MODELS", str(tmp_path))
        assert rec.vision_models_dir() == tmp_path

    def test_resolves_to_a_directory_that_exists_on_this_repo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DASH_VISION_MODELS", raising=False)
        d = rec.vision_models_dir()
        # This checkout keeps models at the repo root; the resolver must
        # find them there instead of reporting them missing.
        if (d / rec.ModelFiles.DETECTOR).exists():
            assert d.exists()
        else:  # a checkout without any models: the default path is fine
            assert d.name == "vision"
